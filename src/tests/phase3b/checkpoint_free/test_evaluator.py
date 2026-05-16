from __future__ import annotations

import inspect
import json
import time
from pathlib import Path

import src.runtime.checkpoint_free_evaluator as evaluator
from scripts.run_phase3b_checkpoint_free_evaluator import main as evaluator_cli_main
from src.runtime.checkpoint_free_evaluator import (
    build_checkpoint_free_run_plan,
    run_checkpoint_free_evaluator,
    validate_checkpoint_free_request,
)
from src.search.exact_campaign import ExactCampaign
from src.search.exact_parallel_scheduler import ParallelWaveExecution, WorkerResult


def test_checkpoint_free_plan_from_readiness_fixture(tmp_path: Path, monkeypatch) -> None:
    readiness = _write_readiness_packet(tmp_path)
    monkeypatch.setattr(evaluator, "select_checkpoint_free_wave_entries", _fake_wave_entries)

    plan = build_checkpoint_free_run_plan(
        project_root=tmp_path,
        readiness_packet_path=readiness,
        candidate_id="experimental_13900ks_htoff_3x8_global_normal",
        duration_seconds=300,
        artifact_root=_artifact_root(tmp_path),
        log_root=_log_root(tmp_path),
        run_id="plan_unit",
    )

    assert plan["schema"] == "phase3b-checkpoint-free-evaluator/v0"
    assert plan["duration_seconds"] == 300
    assert plan["candidate_profile"]["process_count"] == 3
    assert plan["candidate_profile"]["env"] == {"EXACT_CP_SAT_WORKERS": "8"}
    assert plan["safety"]["checkpoint_free"] is True
    assert plan["safety"]["main_py_executed"] is False
    assert plan["safety"]["exact_campaign_used"] is False
    assert plan["resource_stop_rules"]["max_total_private_gib"] == 44.0
    assert plan["wave"]["selected_count"] == 2


def test_checkpoint_free_plan_can_lock_explicit_frontier_candidate_key(
    tmp_path: Path,
    monkeypatch,
) -> None:
    readiness = _write_readiness_packet(tmp_path)
    seen: dict[str, object] = {}

    def fake_explicit_wave_entries(**kwargs) -> list[dict[str, object]]:
        seen["wave_candidate_keys"] = kwargs.get("wave_candidate_keys")
        return [
            {
                "candidate": [1344, 42, 32],
                "candidate_key": "42x32",
                "selection_reason": "explicit_candidate_key",
                "wave_slot_index": 0,
            }
        ]

    monkeypatch.setattr(evaluator, "select_checkpoint_free_wave_entries", fake_explicit_wave_entries)

    plan = build_checkpoint_free_run_plan(
        project_root=tmp_path,
        readiness_packet_path=readiness,
        candidate_id="B0_prod_4x4",
        duration_seconds=600,
        artifact_root=_artifact_root(tmp_path),
        log_root=_log_root(tmp_path),
        run_id="explicit_42x32_plan",
        wave_candidate_keys=["42x32"],
    )

    assert seen["wave_candidate_keys"] == ["42x32"]
    assert plan["wave"]["selection_kind"] == "explicit_frontier_candidate_key_v0"
    assert plan["wave"]["requested_candidate_keys"] == ["42x32"]
    assert plan["wave"]["selected_count"] == 1
    assert plan["wave"]["entries"][0]["candidate_key"] == "42x32"


def test_checkpoint_free_plan_can_exclude_hotspot_candidate_keys(
    tmp_path: Path,
    monkeypatch,
) -> None:
    readiness = _write_readiness_packet(tmp_path)
    seen: dict[str, object] = {}

    def fake_reduced_wave_entries(**kwargs) -> list[dict[str, object]]:
        seen["exclude_wave_candidate_keys"] = kwargs.get("exclude_wave_candidate_keys")
        return [
            {
                "candidate": [840, 70, 12],
                "candidate_key": "70x12",
                "selection_reason": "objective_head",
                "wave_slot_index": 0,
            },
            {
                "candidate": [1330, 70, 19],
                "candidate_key": "70x19",
                "selection_reason": "anchor_head",
                "wave_slot_index": 1,
            },
        ]

    monkeypatch.setattr(evaluator, "select_checkpoint_free_wave_entries", fake_reduced_wave_entries)

    plan = build_checkpoint_free_run_plan(
        project_root=tmp_path,
        readiness_packet_path=readiness,
        candidate_id="B0_prod_4x4",
        duration_seconds=300,
        artifact_root=_artifact_root(tmp_path),
        log_root=_log_root(tmp_path),
        run_id="exclude_hotspots_plan",
        max_wave_candidates=2,
        exclude_wave_candidate_keys=["42x32", "67x20"],
    )

    assert seen["exclude_wave_candidate_keys"] == ["42x32", "67x20"]
    assert plan["wave"]["selection_kind"] == "deterministic_frontier_bounded_wave_excluding_keys_v0"
    assert plan["wave"]["excluded_candidate_keys"] == ["42x32", "67x20"]
    assert [entry["candidate_key"] for entry in plan["wave"]["entries"]] == ["70x12", "70x19"]


def test_checkpoint_free_explicit_candidate_key_must_be_frontier() -> None:
    entries = evaluator._explicit_frontier_wave_entries(
        {
            "frontier": [(840, 70, 12), (1344, 42, 32)],
            "frontier_probe_mode": "auto",
        },
        candidate_keys=["42x32"],
    )

    assert [entry["candidate_key"] for entry in entries] == ["42x32"]
    assert entries[0]["selection_reason"] == "explicit_candidate_key"

    try:
        evaluator._explicit_frontier_wave_entries(
            {"frontier": [(840, 70, 12)]},
            candidate_keys=["42x32"],
        )
    except ValueError as exc:
        assert "not in the current frontier" in str(exc)
    else:
        raise AssertionError("non-frontier explicit candidate key should fail")


def test_checkpoint_free_exclusion_filters_and_refills_wave(monkeypatch) -> None:
    calls: list[tuple[int, int]] = []

    def fake_select_entries(_frontier_state, *, parallel_processes, remaining_attempt_budget):
        calls.append((parallel_processes, remaining_attempt_budget))
        return [
            {"candidate": (840, 70, 12), "selection_reason": "objective_head", "wave_slot_index": 0},
            {"candidate": (1344, 42, 32), "selection_reason": "prune_head", "wave_slot_index": 1},
            {"candidate": (1330, 70, 19), "selection_reason": "anchor_head", "wave_slot_index": 2},
            {"candidate": (1340, 67, 20), "selection_reason": "prune_fill", "wave_slot_index": 3},
        ]

    monkeypatch.setattr(evaluator, "_select_parallel_wave_candidate_entries", fake_select_entries)

    entries = evaluator._select_wave_entries_excluding_keys(
        frontier_state={},
        process_count=2,
        max_wave_candidates=2,
        excluded_candidate_keys=["42x32", "67x20"],
    )

    assert calls[0] == (2, 4)
    assert [entry["candidate_key"] for entry in entries] == ["70x12", "70x19"]
    assert [entry["wave_slot_index"] for entry in entries] == [0, 1]
    assert [entry["original_wave_slot_index"] for entry in entries] == [0, 2]


def test_checkpoint_free_rejects_explicit_and_excluded_overlap(tmp_path: Path) -> None:
    readiness = _write_readiness_packet(tmp_path)

    try:
        build_checkpoint_free_run_plan(
            project_root=tmp_path,
            readiness_packet_path=readiness,
            candidate_id="B0_prod_4x4",
            duration_seconds=300,
            artifact_root=_artifact_root(tmp_path),
            log_root=_log_root(tmp_path),
            run_id="bad_overlap_plan",
            wave_candidate_keys=["42x32"],
            exclude_wave_candidate_keys=["42x32"],
        )
    except ValueError as exc:
        assert "overlap" in str(exc)
    else:
        raise AssertionError("overlapping explicit/excluded keys should fail")


def test_checkpoint_free_cli_plan_only_and_guards(tmp_path: Path, monkeypatch) -> None:
    readiness = _write_readiness_packet(tmp_path)
    monkeypatch.setattr(evaluator, "select_checkpoint_free_wave_entries", _fake_wave_entries)
    artifact_root = _artifact_root(tmp_path)
    log_root = _log_root(tmp_path)

    rc = evaluator_cli_main(
        [
            "--project-root",
            str(tmp_path),
            "--readiness-packet",
            str(readiness),
            "--candidate-id",
            "B0_prod_4x4",
            "--duration-seconds",
            "300",
            "--run-id",
            "cli_plan_only",
            "--artifact-root",
            str(artifact_root),
            "--log-root",
            str(log_root),
            "--plan-only",
        ]
    )

    assert rc == 0
    summary = json.loads(
        (artifact_root / "cli_plan_only" / "run_summary.json").read_text(encoding="utf-8")
    )
    assert summary["status"] == "planned_only"
    assert summary["execute"] is False
    assert summary["checkpoint_written"] is False
    assert summary["resource_stop_rules"]["max_total_private_gib"] == 44.0
    assert "Resource stop max private GiB: `44.0`" in (
        artifact_root / "cli_plan_only" / "run_summary.md"
    ).read_text(encoding="utf-8")

    assert (
        evaluator_cli_main(
            [
                "--project-root",
                str(tmp_path),
                "--readiness-packet",
                str(readiness),
                "--artifact-root",
                str(artifact_root),
                "--log-root",
                str(log_root),
                "--duration-seconds",
                "168",
            ]
        )
        == 2
    )
    assert (
        evaluator_cli_main(
            [
                "--project-root",
                str(tmp_path),
                "--readiness-packet",
                str(readiness),
                "--artifact-root",
                str(artifact_root),
                "--log-root",
                str(log_root),
                "--resume-campaign",
            ]
        )
        == 2
    )


def test_checkpoint_free_execute_uses_scheduler_without_checkpoint_state(
    tmp_path: Path,
    monkeypatch,
) -> None:
    readiness = _write_readiness_packet(tmp_path)
    monkeypatch.setattr(evaluator, "select_checkpoint_free_wave_entries", _fake_wave_entries)
    monkeypatch.setattr(
        ExactCampaign,
        "load_or_create",
        classmethod(lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("campaign used"))),
    )
    calls: dict[str, object] = {}

    def factory(**kwargs):
        calls["factory_kwargs"] = kwargs
        return _FakePool(project_root=tmp_path)

    summary = run_checkpoint_free_evaluator(
        project_root=tmp_path,
        readiness_packet_path=readiness,
        candidate_id="B0_prod_4x4",
        duration_seconds=300,
        execute=True,
        artifact_root=_artifact_root(tmp_path),
        log_root=_log_root(tmp_path),
        run_id="execute_mock",
        worker_pool_factory=factory,
        sample_interval_seconds=0.01,
    )

    assert summary["status"] == "completed"
    assert summary["exact_campaign_used"] is False
    assert summary["main_py_executed"] is False
    diagnostics = summary["execution"]["wave_result_diagnostics"]
    assert diagnostics["planned_candidate_keys"] == ["70x70", "70x69"]
    assert diagnostics["completed_candidate_keys"] == ["70x70"]
    assert diagnostics["pending_candidate_keys"] == ["70x69"]
    assert diagnostics["proof_source"] is False
    assert calls["factory_kwargs"]["solve_mode"] == "certified_exact"
    assert _FakePool.seen_preloaded_cut_counts == [0, 0]
    results = (
        _artifact_root(tmp_path)
        / "execute_mock"
        / "checkpoint_free_eval_results.jsonl"
    ).read_text(encoding="utf-8")
    assert "70x70" in results
    assert "load_or_create" not in inspect.getsource(evaluator)


def test_checkpoint_free_writes_stage_heartbeats_from_worker_pool(
    tmp_path: Path,
    monkeypatch,
) -> None:
    readiness = _write_readiness_packet(tmp_path)
    monkeypatch.setattr(evaluator, "select_checkpoint_free_wave_entries", _fake_wave_entries)

    def factory(**_kwargs):
        return _HeartbeatFakePool(project_root=tmp_path)

    summary = run_checkpoint_free_evaluator(
        project_root=tmp_path,
        readiness_packet_path=readiness,
        candidate_id="B0_prod_4x4",
        duration_seconds=300,
        execute=True,
        artifact_root=_artifact_root(tmp_path),
        log_root=_log_root(tmp_path),
        run_id="heartbeat_mock",
        worker_pool_factory=factory,
        sample_interval_seconds=0.01,
    )

    heartbeat_path = Path(summary["paths"]["stage_heartbeats_jsonl"])
    heartbeat_lines = [
        json.loads(line)
        for line in heartbeat_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert summary["status"] == "completed"
    assert summary["execution"]["stage_heartbeat_count"] == 2
    assert heartbeat_lines[0]["message_type"] == "HEARTBEAT"
    assert heartbeat_lines[0]["candidate_key"] == "70x70"
    assert heartbeat_lines[0]["payload"]["stage"] == "exact_session"
    assert heartbeat_lines[1]["payload"]["stage"] == "master"
    assert "- Stage heartbeats: `2`" in (
        _artifact_root(tmp_path) / "heartbeat_mock" / "run_summary.md"
    ).read_text(encoding="utf-8")


def test_checkpoint_free_sensitive_path_mutation_disqualifies(tmp_path: Path, monkeypatch) -> None:
    readiness = _write_readiness_packet(tmp_path)
    monkeypatch.setattr(evaluator, "select_checkpoint_free_wave_entries", _fake_wave_entries)

    def factory(**_kwargs):
        return _MutatingFakePool(project_root=tmp_path)

    summary = run_checkpoint_free_evaluator(
        project_root=tmp_path,
        readiness_packet_path=readiness,
        candidate_id="B0_prod_4x4",
        duration_seconds=300,
        execute=True,
        artifact_root=_artifact_root(tmp_path),
        log_root=_log_root(tmp_path),
        run_id="mutating_mock",
        worker_pool_factory=factory,
        sample_interval_seconds=0.01,
    )

    assert summary["status"] == "disqualified_sensitive_path_mutation"
    assert "data/checkpoints" in summary["sensitive_path_comparison"]["changed_paths"]
    assert "data/checkpoints/exact_campaign_state.json" in summary["sensitive_path_comparison"][
        "changed_paths"
    ]


def test_checkpoint_free_resource_stop_terminates_pool(tmp_path: Path, monkeypatch) -> None:
    readiness = _write_readiness_packet(tmp_path)
    monkeypatch.setattr(evaluator, "select_checkpoint_free_wave_entries", _fake_wave_entries)
    pool = _ResourceStopFakePool(project_root=tmp_path)

    def factory(**_kwargs):
        return pool

    summary = run_checkpoint_free_evaluator(
        project_root=tmp_path,
        readiness_packet_path=readiness,
        candidate_id="B0_prod_4x4",
        duration_seconds=300,
        execute=True,
        artifact_root=_artifact_root(tmp_path),
        log_root=_log_root(tmp_path),
        run_id="resource_stop_mock",
        worker_pool_factory=factory,
        sample_interval_seconds=0.01,
        max_total_private_gib=0.000001,
    )

    assert summary["status"] == "stopped_resource_limit"
    assert summary["execution"]["failure_reason"] == "checkpoint_free_resource_stop_limit_exceeded"
    assert summary["execution"]["resource_stop_triggered"] is True
    assert summary["execution"]["resource_stop"]["exceeded_metric"] == "total_private_bytes"
    assert pool.terminated is True
    assert summary["sensitive_path_comparison"]["changed"] is False


def test_checkpoint_free_wave_diagnostics_marks_timeout_stragglers() -> None:
    tasks = evaluator.build_parallel_worker_tasks(
        candidates=[(4900, 70, 70), (4830, 70, 69)],
        attempt_start=0,
        attempt_indices=[1, 2],
        master_seconds=300.0,
        binding_seconds=300.0,
        routing_seconds=300.0,
        flow_seconds=60.0,
        benders_max_iter=30,
        preloaded_cut_map={},
    )
    wave = ParallelWaveExecution(
        completed=False,
        failure_reason="checkpoint_free_wave_timeout",
        results=(
            WorkerResult(
                dispatch_seq=0,
                attempt_index=1,
                candidate=(4900, 70, 70),
                status="INFEASIBLE",
                solution=None,
                proof_summary={},
                exact_safe_cuts=[],
                loaded_exact_safe_cut_count=0,
                generated_exact_safe_cut_count=0,
                worker_wall_seconds=0.1,
                peak_rss_bytes=123,
                error=None,
            ),
        ),
        dispatched_candidate_keys=("70x70", "70x69"),
        elapsed_seconds=300.0,
        peak_rss_bytes_external_total=123,
        peak_rss_bytes_internal_max_single_process=123,
    )

    diagnostics = evaluator._wave_result_diagnostics(
        tasks=tasks,
        wave_execution=wave,
        timed_out=True,
        resource_stopped=False,
    )

    assert diagnostics["planned_count"] == 2
    assert diagnostics["completed_candidate_keys"] == ["70x70"]
    assert diagnostics["pending_candidate_keys"] == ["70x69"]
    assert diagnostics["straggler_candidate_keys"] == ["70x69"]
    assert diagnostics["interrupted_candidate_keys"] == []
    assert diagnostics["status_counts"] == {"INFEASIBLE": 1}


def test_checkpoint_free_namespace_guard_rejects_bad_outputs(tmp_path: Path) -> None:
    guard = validate_checkpoint_free_request(
        duration_seconds=300,
        artifact_root=tmp_path / "release",
        log_root=_log_root(tmp_path),
        extra_tokens=["--checkpoint-output"],
    )

    assert guard["allowed"] is False
    assert any("artifact_root" in reason for reason in guard["reasons"])
    assert any("forbidden_cli_token" in reason for reason in guard["reasons"])


def _write_readiness_packet(root: Path) -> Path:
    path = (
        root
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "07_short_run_readiness"
        / "short_run_readiness_packet.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "phase3b-short-run-readiness-packet/v0",
        "allowed_durations_seconds": [300, 600],
        "candidates": [
            {
                "candidate_id": "B0_prod_4x4",
                "source_kind": "s5_config_manifest",
                "source_profile_id": "B0_prod_4x4",
                "process_count": 4,
                "env": {"EXACT_CP_SAT_WORKERS": "4"},
                "risk": {"level": "low"},
                "frontier_probe_mode": "auto",
            },
            {
                "candidate_id": "experimental_13900ks_htoff_3x8_global_normal",
                "source_kind": "s5_config_manifest",
                "source_profile_id": "experimental_13900ks_htoff_3x8_global_normal",
                "process_count": 3,
                "env": {"EXACT_CP_SAT_WORKERS": "8"},
                "risk": {"level": "medium"},
                "frontier_probe_mode": "auto",
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _fake_wave_entries(**_kwargs) -> list[dict[str, object]]:
    return [
        {
            "candidate": [4900, 70, 70],
            "candidate_key": "70x70",
            "selection_reason": "objective_head",
            "wave_slot_index": 0,
        },
        {
            "candidate": [4830, 70, 69],
            "candidate_key": "70x69",
            "selection_reason": "prune_head",
            "wave_slot_index": 1,
        },
    ]


class _FakePool:
    seen_preloaded_cut_counts: list[int] = []

    def __init__(self, *, project_root: Path) -> None:
        self.project_root = Path(project_root)

    def run_wave(self, tasks) -> ParallelWaveExecution:
        type(self).seen_preloaded_cut_counts = [
            len(tuple(task.preloaded_exact_safe_cuts)) for task in tasks
        ]
        return ParallelWaveExecution(
            completed=True,
            failure_reason=None,
            results=(
                WorkerResult(
                    dispatch_seq=0,
                    attempt_index=1,
                    candidate=(4900, 70, 70),
                    status="UNKNOWN",
                    solution=None,
                    proof_summary={"mode": "certified_exact"},
                    exact_safe_cuts=[],
                    loaded_exact_safe_cut_count=0,
                    generated_exact_safe_cut_count=0,
                    worker_wall_seconds=0.01,
                    peak_rss_bytes=123,
                    error=None,
                ),
            ),
            dispatched_candidate_keys=("70x70",),
            elapsed_seconds=0.01,
            peak_rss_bytes_external_total=123,
            peak_rss_bytes_internal_max_single_process=123,
        )

    def close(self) -> None:
        return None

    def terminate(self) -> None:
        return None


class _MutatingFakePool(_FakePool):
    def run_wave(self, tasks) -> ParallelWaveExecution:
        checkpoint = self.project_root / "data" / "checkpoints" / "exact_campaign_state.json"
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        checkpoint.write_text("{}", encoding="utf-8")
        return super().run_wave(tasks)


class _HeartbeatFakePool(_FakePool):
    def run_wave(self, tasks) -> ParallelWaveExecution:
        wave = super().run_wave(tasks)
        return ParallelWaveExecution(
            completed=wave.completed,
            failure_reason=wave.failure_reason,
            results=wave.results,
            dispatched_candidate_keys=wave.dispatched_candidate_keys,
            elapsed_seconds=wave.elapsed_seconds,
            peak_rss_bytes_external_total=wave.peak_rss_bytes_external_total,
            peak_rss_bytes_internal_max_single_process=wave.peak_rss_bytes_internal_max_single_process,
            heartbeat_events=(
                {
                    "message_type": "HEARTBEAT",
                    "worker_index": 0,
                    "dispatch_seq": 0,
                    "attempt_index": 1,
                    "candidate": [4900, 70, 70],
                    "candidate_key": "70x70",
                    "payload": {
                        "schema_version": 1,
                        "stage": "exact_session",
                        "event": "start",
                    },
                },
                {
                    "message_type": "HEARTBEAT",
                    "worker_index": 0,
                    "dispatch_seq": 0,
                    "attempt_index": 1,
                    "candidate": [4900, 70, 70],
                    "candidate_key": "70x70",
                    "payload": {
                        "schema_version": 1,
                        "stage": "master",
                        "event": "start",
                    },
                },
            ),
        )


class _ResourceStopFakePool(_FakePool):
    def __init__(self, *, project_root: Path) -> None:
        super().__init__(project_root=project_root)
        self.terminated = False

    def run_wave(self, tasks) -> ParallelWaveExecution:
        started = time.time()
        while not self.terminated and time.time() - started < 5.0:
            time.sleep(0.01)
        return ParallelWaveExecution(
            completed=False,
            failure_reason="terminated_for_resource_stop" if self.terminated else "not_terminated",
            results=tuple(),
            dispatched_candidate_keys=tuple(task.candidate_key for task in tasks),
            elapsed_seconds=float(time.time() - started),
            peak_rss_bytes_external_total=0,
            peak_rss_bytes_internal_max_single_process=0,
        )

    def terminate(self) -> None:
        self.terminated = True

    def close(self) -> None:
        self.terminated = True


def _artifact_root(root: Path) -> Path:
    return root / ".artifacts" / "phase3b_local_13900ks_tuning_20260430" / "08_checkpoint_free_evaluator"


def _log_root(root: Path) -> Path:
    return (
        root
        / ".codex_test_logs"
        / "phase3b"
        / "local_13900ks_tuning_20260430"
        / "08_checkpoint_free_evaluator"
    )

from __future__ import annotations

import json
import queue
from dataclasses import fields
from pathlib import Path

import src.search.certified_frontier as certified_frontier_module
import src.search.outer_search as outer_search_module
from src.models.cut_manager import (
    RUN_STATUS_CERTIFIED,
    RUN_STATUS_INFEASIBLE,
    RUN_STATUS_UNKNOWN,
    RUN_STATUS_UNPROVEN,
)
from src.search.exact_campaign import ExactCampaign
from src.search.exact_parallel_scheduler import (
    ExactParallelWorkerPool,
    ParallelWaveExecution,
    WorkerResult,
    WorkerTask,
    build_parallel_worker_tasks,
)
from src.search.campaign_telemetry import campaign_telemetry_output_path
from src.search.outer_search import generate_candidate_sizes, run_outer_search


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _build_empty_frontier_project(
    project_root: Path,
    *,
    width: int = 6,
    height: int = 6,
) -> Path:
    _write_json(
        project_root / "rules" / "canonical_rules.json",
        {
            "globals": {"grid": {"width": width, "height": height}, "empty_rectangle": {"objective": "max_lex_area_min_side", "min_side_admissibility": 1}},
            "facility_templates": {
                "synthetic": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            },
        },
    )
    # 单个真实 pose 让 terminal CERTIFIED 场景能走通 blueprint 导出/反查校验链
    # (V73+ 的 manifest 校验会把 blueprint facility 反查回 facility_pools)。
    _write_json(
        project_root / "data" / "preprocessed" / "candidate_placements.json",
        {
            "facility_pools": {
                "synthetic": [
                    {
                        "pose_id": "synthetic_pose_0",
                        "anchor": {"x": 0, "y": 0},
                        "occupied_cells": [[0, 0]],
                        "input_port_cells": [],
                        "output_port_cells": [],
                        "power_coverage_cells": None,
                        "pose_params": {"orientation": 0, "port_mode": "default"},
                    }
                ]
            }
        },
    )
    _write_json(project_root / "data" / "preprocessed" / "mandatory_exact_instances.json", [])
    _write_json(project_root / "data" / "preprocessed" / "all_facility_instances.json", [])
    _write_json(
        project_root / "data" / "preprocessed" / "generic_io_requirements.json",
        {"required_generic_outputs": {}, "required_generic_inputs": {}},
    )
    return project_root


def _read_campaign_state(project_root: Path) -> dict:
    return json.loads(
        (project_root / "data" / "checkpoints" / "exact_campaign_state.json").read_text(
            encoding="utf-8"
        )
    )


def _read_campaign_telemetry(project_root: Path) -> dict:
    path = campaign_telemetry_output_path(
        project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


class _DummyParallelWorkerPool:
    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs

    def close(self) -> None:
        return None


class _SyntheticTaskQueue:
    def put(self, item: object) -> None:
        return None


class _SyntheticResultQueue:
    def __init__(self, messages: list[dict[str, object]]) -> None:
        self._messages = list(messages)

    def get(self, timeout: float | None = None) -> dict[str, object]:
        del timeout
        if not self._messages:
            raise queue.Empty()
        return self._messages.pop(0)

    def get_nowait(self) -> dict[str, object]:
        if not self._messages:
            raise queue.Empty()
        return self._messages.pop(0)


def test_parallel_wave_selection_diversifies_and_deduplicates_heads() -> None:
    frontier_state = {
        "frontier": [
            (30, 6, 5),
            (28, 7, 4),
            (24, 8, 3),
            (20, 5, 4),
            (18, 6, 3),
        ],
        "frontier_metrics_by_key": {
            "6x5": {
                "selection_score_num": 100,
                "selection_score_den": 1,
                "certification_prune_gain": 100,
                "infeasible_prune_gain": 1,
                "anchor_count": 50,
            },
            "7x4": {
                "selection_score_num": 90,
                "selection_score_den": 1,
                "certification_prune_gain": 90,
                "infeasible_prune_gain": 1,
                "anchor_count": 40,
            },
            "8x3": {
                "selection_score_num": 10,
                "selection_score_den": 1,
                "certification_prune_gain": 10,
                "infeasible_prune_gain": 1,
                "anchor_count": 1,
            },
            "5x4": {
                "selection_score_num": 80,
                "selection_score_den": 1,
                "certification_prune_gain": 80,
                "infeasible_prune_gain": 1,
                "anchor_count": 60,
            },
            "6x3": {
                "selection_score_num": 70,
                "selection_score_den": 1,
                "certification_prune_gain": 70,
                "infeasible_prune_gain": 1,
                "anchor_count": 70,
            },
        },
    }

    entries = outer_search_module._select_parallel_wave_candidate_entries(
        frontier_state,
        parallel_processes=4,
        remaining_attempt_budget=4,
    )

    assert [tuple(entry["candidate"]) for entry in entries] == [
        (30, 6, 5),
        (28, 7, 4),
        (24, 8, 3),
        (20, 5, 4),
    ]
    assert [entry["selection_reason"] for entry in entries] == [
        "objective_head",
        "prune_head",
        "anchor_head",
        "prune_fill",
    ]
    assert [int(entry["wave_slot_index"]) for entry in entries] == [0, 1, 2, 3]

    selected = outer_search_module._select_parallel_wave_candidates(
        frontier_state,
        parallel_processes=4,
        remaining_attempt_budget=4,
    )
    assert selected == [tuple(entry["candidate"]) for entry in entries]


def test_parallel_wave_selection_injects_probe_candidate_once_when_present() -> None:
    frontier_state = {
        "potential_domain": [
            (30, 6, 5),
            (28, 7, 4),
            (24, 8, 3),
            (20, 5, 4),
            (18, 6, 3),
        ],
        "frontier": [
            (30, 6, 5),
            (28, 7, 4),
            (24, 8, 3),
            (18, 6, 3),
        ],
        "frontier_probe_mode": "auto",
        "probe_candidate": (20, 5, 4),
        "probe_resume_pending": True,
        "probe_candidate_metrics": {
            "selection_score_num": 50,
            "selection_score_den": 1,
            "certification_prune_gain": 27,
            "infeasible_prune_gain": 10,
            "anchor_count": 72,
            "probe_candidate": 1,
            "probe_prune_gain": 27,
            "probe_resume_pending": 1,
        },
        "frontier_metrics_by_key": {
            "6x5": {
                "selection_score_num": 100,
                "selection_score_den": 1,
                "certification_prune_gain": 100,
                "infeasible_prune_gain": 1,
                "anchor_count": 50,
            },
            "7x4": {
                "selection_score_num": 90,
                "selection_score_den": 1,
                "certification_prune_gain": 90,
                "infeasible_prune_gain": 1,
                "anchor_count": 40,
            },
            "8x3": {
                "selection_score_num": 10,
                "selection_score_den": 1,
                "certification_prune_gain": 10,
                "infeasible_prune_gain": 1,
                "anchor_count": 1,
            },
            "5x4": {
                "selection_score_num": 50,
                "selection_score_den": 1,
                "certification_prune_gain": 27,
                "infeasible_prune_gain": 10,
                "anchor_count": 72,
                "probe_candidate": 1,
                "probe_prune_gain": 27,
                "probe_resume_pending": 1,
            },
            "6x3": {
                "selection_score_num": 70,
                "selection_score_den": 1,
                "certification_prune_gain": 70,
                "infeasible_prune_gain": 1,
                "anchor_count": 70,
            },
        },
    }

    entries = outer_search_module._select_parallel_wave_candidate_entries(
        frontier_state,
        parallel_processes=4,
        remaining_attempt_budget=4,
    )

    assert [tuple(entry["candidate"]) for entry in entries] == [
        (20, 5, 4),
        (30, 6, 5),
        (28, 7, 4),
        (24, 8, 3),
    ]
    assert [entry["selection_reason"] for entry in entries] == [
        "probe_head",
        "objective_head",
        "prune_head",
        "anchor_head",
    ]
    assert entries[0]["probe_candidate"] is True
    assert entries[0]["probe_prune_gain"] == 27
    assert entries[0]["probe_resume_pending"] is True
    assert len({entry["candidate"] for entry in entries}) == len(entries)


def test_parallel_wave_selection_uses_deeper_parallel_depth_multiplier() -> None:
    sorted_frontier = [
        (72, 12, 6),
        (70, 10, 7),
        (63, 9, 7),
        (56, 8, 7),
        (54, 9, 6),
        (48, 8, 6),
        (42, 7, 6),
        (36, 6, 6),
        (35, 7, 5),
    ]
    frontier_state = {
        "frontier": [
            sorted_frontier[4],
            sorted_frontier[1],
            sorted_frontier[8],
            sorted_frontier[0],
            sorted_frontier[6],
            sorted_frontier[3],
            sorted_frontier[7],
            sorted_frontier[2],
            sorted_frontier[5],
        ],
        "frontier_metrics_by_key": {
            "12x6": {
                "selection_score_num": 90,
                "selection_score_den": 1,
                "certification_prune_gain": 90,
                "infeasible_prune_gain": 1,
                "anchor_count": 10,
            },
            "10x7": {
                "selection_score_num": 80,
                "selection_score_den": 1,
                "certification_prune_gain": 80,
                "infeasible_prune_gain": 1,
                "anchor_count": 20,
            },
            "9x7": {
                "selection_score_num": 70,
                "selection_score_den": 1,
                "certification_prune_gain": 70,
                "infeasible_prune_gain": 1,
                "anchor_count": 30,
            },
            "8x7": {
                "selection_score_num": 60,
                "selection_score_den": 1,
                "certification_prune_gain": 60,
                "infeasible_prune_gain": 1,
                "anchor_count": 40,
            },
            "9x6": {
                "selection_score_num": 50,
                "selection_score_den": 1,
                "certification_prune_gain": 50,
                "infeasible_prune_gain": 1,
                "anchor_count": 50,
            },
            "8x6": {
                "selection_score_num": 40,
                "selection_score_den": 1,
                "certification_prune_gain": 40,
                "infeasible_prune_gain": 1,
                "anchor_count": 60,
            },
            "7x6": {
                "selection_score_num": 30,
                "selection_score_den": 1,
                "certification_prune_gain": 30,
                "infeasible_prune_gain": 1,
                "anchor_count": 70,
            },
            "6x6": {
                "selection_score_num": 20,
                "selection_score_den": 1,
                "certification_prune_gain": 20,
                "infeasible_prune_gain": 1,
                "anchor_count": 80,
            },
            "7x5": {
                "selection_score_num": 10,
                "selection_score_den": 1,
                "certification_prune_gain": 10,
                "infeasible_prune_gain": 1,
                "anchor_count": 90,
            },
        },
    }

    selected = outer_search_module._select_parallel_wave_candidates(
        frontier_state,
        parallel_processes=4,
        remaining_attempt_budget=8,
    )

    assert selected == outer_search_module._sorted_frontier_candidates(frontier_state)[:8]
    assert len(selected) == 8


def test_worker_tasks_never_carry_campaign_state() -> None:
    preloaded_cut_map = {
        "2x1": [
            {
                "schema_version": 2,
                "cut_type": "routing_front_blocked_nogood",
                "conflict_set": {"pose_optional::power_pole::pole_0": 0},
                "iteration": 1,
                "metadata": {"kind": "placement_local_nogood"},
            }
        ]
    }
    tasks = build_parallel_worker_tasks(
        candidates=[(2, 2, 1)],
        attempt_start=0,
        master_seconds=30.0,
        binding_seconds=30.0,
        routing_seconds=30.0,
        flow_seconds=30.0,
        benders_max_iter=6,
        preloaded_cut_map=preloaded_cut_map,
    )

    assert len(tasks) == 1
    assert tasks[0].candidate_key == "2x1"
    assert tasks[0].disable_master_warm_start is False
    assert tasks[0].preloaded_exact_safe_cuts[0]["cut_type"] == "routing_front_blocked_nogood"
    # Guard: WorkerTask 必须只携带 primitive / 不可变 dispatch 数据,
    # 不能藏 campaign instance / mutable cut bucket / 求解器 session 等.
    # epsilon_stage 是 P1 #7 main 加的 wave-level ε tag (Optional[float] 默认 None),
    # primitive 数字字段, 不属于 campaign 状态对象, 守卫语义保持.
    assert {field.name for field in fields(WorkerTask)} == {
        "dispatch_seq",
        "attempt_index",
        "candidate",
        "master_seconds",
        "binding_seconds",
        "routing_seconds",
        "flow_seconds",
        "benders_max_iter",
        "disable_master_warm_start",
        "preloaded_exact_safe_cuts",
        "epsilon_stage",
    }


def test_parallel_merge_is_deterministic_under_out_of_order_worker_completion(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_empty_frontier_project(tmp_path / "parallel_deterministic")

    def fake_wave_executor(*, pool, tasks):
        assert isinstance(pool, _DummyParallelWorkerPool)
        first, second = tasks
        return ParallelWaveExecution(
            completed=True,
            failure_reason=None,
            results=(
                WorkerResult(
                    dispatch_seq=second.dispatch_seq,
                    attempt_index=second.attempt_index,
                    candidate=second.candidate,
                    status=RUN_STATUS_UNKNOWN,
                    solution=None,
                    proof_summary={"master_status": RUN_STATUS_UNKNOWN},
                    exact_safe_cuts=[],
                    loaded_exact_safe_cut_count=0,
                    generated_exact_safe_cut_count=0,
                    worker_wall_seconds=0.01,
                    peak_rss_bytes=1,
                    error=None,
                ),
                WorkerResult(
                    dispatch_seq=first.dispatch_seq,
                    attempt_index=first.attempt_index,
                    candidate=first.candidate,
                    status=RUN_STATUS_UNPROVEN,
                    solution=None,
                    proof_summary={"master_status": RUN_STATUS_UNPROVEN},
                    exact_safe_cuts=[],
                    loaded_exact_safe_cut_count=0,
                    generated_exact_safe_cut_count=0,
                    worker_wall_seconds=0.01,
                    peak_rss_bytes=1,
                    error=None,
                ),
            ),
            dispatched_candidate_keys=tuple(task.candidate_key for task in tasks),
            elapsed_seconds=0.02,
            peak_rss_bytes_external_total=2,
            peak_rss_bytes_internal_max_single_process=1,
        )

    monkeypatch.setattr(outer_search_module, "ExactParallelWorkerPool", _DummyParallelWorkerPool)
    monkeypatch.setattr(outer_search_module, "run_parallel_exact_campaign_wave", fake_wave_executor)

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        max_attempts=2,
        min_side=1,
        area_upper_bound=9,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
        parallel_processes=2,
    )

    assert status == RUN_STATUS_UNPROVEN
    assert result is None
    state = _read_campaign_state(project_root)
    assert state["last_stop_reason"]["reason"] == "candidate_returned_unproven"
    assert sorted(record["status"] for record in state["candidates"].values()) == [
        RUN_STATUS_UNKNOWN,
        RUN_STATUS_UNPROVEN,
    ]
    telemetry = _read_campaign_telemetry(project_root)
    assert telemetry["aggregate"]["wave_count"] == 1
    assert telemetry["aggregate"]["status_counts"] == {
        RUN_STATUS_UNPROVEN: 1,
        RUN_STATUS_UNKNOWN: 1,
    }
    assert telemetry["aggregate"]["outcome_counts"] == {
        "unproven": 1,
        "unknown": 1,
    }
    assert telemetry["aggregate"]["selection_reason_counts"] == {
        "objective_head": 1,
        "prune_head": 1,
    }
    assert telemetry["aggregate"]["master_status_counts"] == {
        RUN_STATUS_UNPROVEN: 1,
        RUN_STATUS_UNKNOWN: 1,
    }
    assert [entry["status"] for entry in telemetry["waves"][0]["candidate_results"]] == [
        RUN_STATUS_UNPROVEN,
        RUN_STATUS_UNKNOWN,
    ]
    assert [entry["selection_reason"] for entry in telemetry["waves"][0]["candidate_results"]] == [
        "objective_head",
        "prune_head",
    ]
    assert [entry["wave_slot_index"] for entry in telemetry["waves"][0]["candidate_results"]] == [0, 1]


def test_parallel_worker_pool_rejects_result_candidate_mismatch() -> None:
    tasks = [
        WorkerTask(0, 1, (9, 3, 3), 1.0, 1.0, 1.0, 1.0, 1, False, tuple()),
        WorkerTask(1, 2, (4, 2, 2), 1.0, 1.0, 1.0, 1.0, 1, False, tuple()),
    ]
    pool = ExactParallelWorkerPool.__new__(ExactParallelWorkerPool)
    pool._closed = False
    pool._started = True
    pool._processes = []
    pool._task_queue = _SyntheticTaskQueue()
    pool._result_queue = _SyntheticResultQueue(
        [
            {
                "message_type": "RESULT",
                "result": WorkerResult(
                    dispatch_seq=0,
                    attempt_index=1,
                    candidate=(1, 1, 1),
                    status=RUN_STATUS_INFEASIBLE,
                    solution=None,
                    proof_summary={"master_status": RUN_STATUS_INFEASIBLE},
                    exact_safe_cuts=[],
                    loaded_exact_safe_cut_count=0,
                    generated_exact_safe_cut_count=0,
                    worker_wall_seconds=0.01,
                    peak_rss_bytes=1,
                    error=None,
                ),
            },
            {
                "message_type": "RESULT",
                "result": WorkerResult(
                    dispatch_seq=1,
                    attempt_index=2,
                    candidate=(4, 2, 2),
                    status=RUN_STATUS_INFEASIBLE,
                    solution=None,
                    proof_summary={"master_status": RUN_STATUS_INFEASIBLE},
                    exact_safe_cuts=[],
                    loaded_exact_safe_cut_count=0,
                    generated_exact_safe_cut_count=0,
                    worker_wall_seconds=0.01,
                    peak_rss_bytes=1,
                    error=None,
                ),
            },
        ]
    )
    pool.rss_sample_interval_seconds = 0.01
    pool._total_crash_respawns = 0
    pool.start = lambda: None
    pool._respawn_all_workers = lambda: None
    pool.terminate = lambda: None
    pool._sum_process_tree_rss = lambda: 0

    wave = ExactParallelWorkerPool.run_wave(pool, tasks)

    assert wave.completed is False
    assert wave.failure_reason == "worker_result_candidate_mismatch:0"
    assert wave.dispatched_candidate_keys == ("3x3", "2x2")
    assert all(result.candidate_key != "1x1" for result in wave.results)


def test_parallel_worker_pool_drops_errored_strong_result() -> None:
    task = WorkerTask(0, 1, (9, 3, 3), 1.0, 1.0, 1.0, 1.0, 1, False, tuple())
    pool = ExactParallelWorkerPool.__new__(ExactParallelWorkerPool)
    pool._closed = False
    pool._started = True
    pool._processes = []
    pool._task_queue = _SyntheticTaskQueue()
    pool._result_queue = _SyntheticResultQueue(
        [
            {
                "message_type": "RESULT",
                "result": WorkerResult(
                    dispatch_seq=0,
                    attempt_index=1,
                    candidate=(9, 3, 3),
                    status=RUN_STATUS_CERTIFIED,
                    solution={"ghost_pick": {"anchor": {"x": 0, "y": 0}}},
                    proof_summary={"master_status": RUN_STATUS_CERTIFIED},
                    exact_safe_cuts=[],
                    loaded_exact_safe_cut_count=0,
                    generated_exact_safe_cut_count=0,
                    worker_wall_seconds=0.01,
                    peak_rss_bytes=1,
                    error="RuntimeError: synthetic crash after partial result",
                ),
            },
        ]
    )
    pool.rss_sample_interval_seconds = 0.01
    pool._total_crash_respawns = 0
    pool.start = lambda: None
    pool._respawn_all_workers = lambda: None
    pool.terminate = lambda: None
    pool._sum_process_tree_rss = lambda: 0

    wave = ExactParallelWorkerPool.run_wave(pool, [task])

    assert wave.completed is False
    assert wave.failure_reason == "RuntimeError: synthetic crash after partial result"
    assert wave.results == ()


def test_outer_search_rejects_wave_result_candidate_mismatch(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_empty_frontier_project(tmp_path / "outer_wave_mismatch")

    def fake_wave_executor(*, pool, tasks):
        assert isinstance(pool, _DummyParallelWorkerPool)
        first = tasks[0]
        return ParallelWaveExecution(
            completed=True,
            failure_reason=None,
            results=(
                WorkerResult(
                    dispatch_seq=first.dispatch_seq,
                    attempt_index=first.attempt_index,
                    candidate=(1, 1, 1),
                    status=RUN_STATUS_INFEASIBLE,
                    solution=None,
                    proof_summary={"master_status": RUN_STATUS_INFEASIBLE},
                    exact_safe_cuts=[],
                    loaded_exact_safe_cut_count=0,
                    generated_exact_safe_cut_count=0,
                    worker_wall_seconds=0.01,
                    peak_rss_bytes=1,
                    error=None,
                ),
            ),
            dispatched_candidate_keys=tuple(task.candidate_key for task in tasks),
            elapsed_seconds=0.02,
            peak_rss_bytes_external_total=2,
            peak_rss_bytes_internal_max_single_process=1,
        )

    monkeypatch.setattr(outer_search_module, "ExactParallelWorkerPool", _DummyParallelWorkerPool)
    monkeypatch.setattr(outer_search_module, "run_parallel_exact_campaign_wave", fake_wave_executor)

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        max_attempts=2,
        min_side=1,
        area_upper_bound=9,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
        parallel_processes=2,
    )

    assert status == RUN_STATUS_UNKNOWN
    assert result is None
    state = _read_campaign_state(project_root)
    assert state["last_stop_reason"]["reason"] == "worker_process_failed"
    assert "1x1" not in state["candidates"]
    telemetry = _read_campaign_telemetry(project_root)
    assert telemetry["waves"][0]["completed"] is False
    assert telemetry["waves"][0]["failure_reason"] == (
        "parallel_wave_result_candidate_mismatch:0"
    )
    assert telemetry["waves"][0]["candidate_results"] == []


def test_worker_failure_preserves_completed_progress_and_keeps_campaign_readable(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_empty_frontier_project(tmp_path / "parallel_worker_failure")

    def fake_wave_executor(*, pool, tasks):
        first = tasks[0]
        return ParallelWaveExecution(
            completed=False,
            failure_reason="worker_process_failed:pid=1:exitcode=1",
            results=(
                WorkerResult(
                    dispatch_seq=first.dispatch_seq,
                    attempt_index=first.attempt_index,
                    candidate=first.candidate,
                    status=RUN_STATUS_INFEASIBLE,
                    solution=None,
                    proof_summary={"master_status": RUN_STATUS_INFEASIBLE},
                    exact_safe_cuts=[],
                    loaded_exact_safe_cut_count=0,
                    generated_exact_safe_cut_count=0,
                    worker_wall_seconds=0.01,
                    peak_rss_bytes=1,
                    error=None,
                ),
            ),
            dispatched_candidate_keys=tuple(task.candidate_key for task in tasks),
            elapsed_seconds=0.02,
            peak_rss_bytes_external_total=2,
            peak_rss_bytes_internal_max_single_process=1,
        )

    monkeypatch.setattr(outer_search_module, "ExactParallelWorkerPool", _DummyParallelWorkerPool)
    monkeypatch.setattr(outer_search_module, "run_parallel_exact_campaign_wave", fake_wave_executor)

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        max_attempts=2,
        min_side=1,
        area_upper_bound=9,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
        parallel_processes=2,
    )

    assert status == RUN_STATUS_UNKNOWN
    assert result is None

    state = _read_campaign_state(project_root)
    statuses = {key: record["status"] for key, record in state["candidates"].items()}
    assert RUN_STATUS_INFEASIBLE in statuses.values()
    assert "RUNNING" in statuses.values()
    assert state["last_stop_reason"]["reason"] == "worker_process_failed"
    telemetry = _read_campaign_telemetry(project_root)
    assert telemetry["aggregate"]["wave_count"] == 1
    assert telemetry["aggregate"]["outcome_counts"]["master_infeasible"] == 1
    assert telemetry["aggregate"]["outcome_counts"]["worker_process_failed"] == 1
    assert telemetry["aggregate"]["selection_reason_counts"] == {"objective_head": 1}
    assert telemetry["aggregate"]["master_status_counts"] == {RUN_STATUS_INFEASIBLE: 1}
    assert telemetry["aggregate"]["failure_reason_counts"] == {
        "worker_process_failed:pid=1:exitcode=1": 1
    }
    assert telemetry["waves"][0]["completed"] is False
    assert telemetry["waves"][0]["candidate_results"][0]["selection_reason"] == "objective_head"
    assert telemetry["waves"][0]["candidate_results"][0]["wave_slot_index"] == 0

    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)
    assert resumed.resumed is True
    assert resumed.compatible_hashes is True


def test_frontier_probe_auto_records_campaign_and_telemetry_and_retries_pending_unknown(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_empty_frontier_project(
        tmp_path / "frontier_probe_resume",
        width=12,
        height=12,
    )
    calls: list[tuple[int, int]] = []

    def fake_run_benders_for_ghost_rect(*, ghost_w: int, ghost_h: int, session=None, **kwargs):
        del session, kwargs
        calls.append((int(ghost_w), int(ghost_h)))
        fake_run_benders_for_ghost_rect.last_run_metadata = {
            "proof_summary": {
                "mode": "certified_exact",
                "master_status": RUN_STATUS_UNKNOWN,
            },
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        }
        return RUN_STATUS_UNKNOWN, None

    fake_run_benders_for_ghost_rect.last_run_metadata = {
        "proof_summary": {},
        "exact_safe_cuts": [],
        "loaded_exact_safe_cut_count": 0,
        "generated_exact_safe_cut_count": 0,
    }

    monkeypatch.setattr(outer_search_module, "run_benders_for_ghost_rect", fake_run_benders_for_ghost_rect)
    monkeypatch.setattr(
        outer_search_module.ExactSearchSession,
        "create",
        staticmethod(lambda project_root, solve_mode="certified_exact": object()),
    )

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        max_attempts=1,
        min_side=1,
        area_upper_bound=60,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
        frontier_probe_mode="auto",
    )

    assert status == RUN_STATUS_UNKNOWN
    assert result is None
    assert calls == [(6, 5)]

    state = _read_campaign_state(project_root)
    assert state["frontier_probe"]["mode"] == "auto"
    assert state["frontier_probe"]["executed_candidate_keys"] == ["6x5"]
    assert state["frontier_probe"]["execution_count"] == 1
    assert state["frontier_probe"]["last_candidate_key"] == "6x5"
    assert state["frontier_probe"]["last_probe_prune_gain"] == 69
    assert state["frontier_probe"]["last_probe_resume_pending"] is False

    candidate_record = state["candidates"]["6x5"]
    assert candidate_record["proof_summary"]["selection_reason"] == outer_search_module.FRONTIER_PROBE_SELECTION_REASON
    assert candidate_record["proof_summary"]["frontier_probe"] == {
        "mode": "auto",
        "probe_candidate": True,
        "probe_resume_pending": False,
        "probe_prune_gain": 69,
    }

    telemetry = _read_campaign_telemetry(project_root)
    assert telemetry["aggregate"]["selection_reason_counts"] == {
        outer_search_module.FRONTIER_PROBE_SELECTION_REASON: 1
    }
    assert telemetry["aggregate"]["probe_mode_counts"] == {"auto": 1}
    assert telemetry["aggregate"]["probe_round_count"] == 1
    assert telemetry["aggregate"]["probe_candidate_count"] == 1
    assert telemetry["aggregate"]["probe_prune_gain_sum"] == 69
    assert telemetry["aggregate"]["probe_prune_gain_max"] == 69
    assert telemetry["aggregate"]["probe_resume_pending_count"] == 0
    assert telemetry["waves"][0]["probe_round_active"] is True
    assert telemetry["waves"][0]["probe_candidate_keys"] == ["6x5"]
    assert telemetry["waves"][0]["probe_prune_gain_sum"] == 69
    assert telemetry["waves"][0]["probe_resume_pending_count"] == 0
    assert telemetry["waves"][0]["candidate_results"][0]["selection_reason"] == outer_search_module.FRONTIER_PROBE_SELECTION_REASON
    assert telemetry["waves"][0]["candidate_results"][0]["frontier_probe_mode"] == "auto"
    assert telemetry["waves"][0]["candidate_results"][0]["probe_candidate"] is True
    assert telemetry["waves"][0]["candidate_results"][0]["probe_prune_gain"] == 69
    assert telemetry["waves"][0]["candidate_results"][0]["probe_resume_pending"] is False

    calls.clear()
    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        max_attempts=1,
        min_side=1,
        area_upper_bound=60,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=True,
        frontier_probe_mode="auto",
    )

    assert status == RUN_STATUS_UNKNOWN
    assert result is None
    assert calls == [(6, 5)]

    state = _read_campaign_state(project_root)
    assert state["frontier_probe"]["executed_candidate_keys"] == ["6x5"]
    assert state["frontier_probe"]["execution_count"] == 1
    assert state["frontier_probe"]["last_candidate_key"] == "6x5"
    assert state["frontier_probe"]["last_probe_prune_gain"] == 69
    assert state["frontier_probe"]["last_probe_resume_pending"] is True

    telemetry = _read_campaign_telemetry(project_root)
    assert telemetry["aggregate"]["selection_reason_counts"] == {
        outer_search_module.FRONTIER_PROBE_SELECTION_REASON: 2
    }
    assert telemetry["aggregate"]["probe_mode_counts"] == {"auto": 2}
    assert telemetry["aggregate"]["probe_round_count"] == 2
    assert telemetry["aggregate"]["probe_candidate_count"] == 2
    assert telemetry["aggregate"]["probe_prune_gain_sum"] == 138
    assert telemetry["aggregate"]["probe_prune_gain_max"] == 69
    assert telemetry["aggregate"]["probe_resume_pending_count"] == 1
    assert telemetry["waves"][-1]["probe_round_active"] is True
    assert telemetry["waves"][-1]["probe_candidate_keys"] == ["6x5"]
    assert telemetry["waves"][-1]["probe_prune_gain_sum"] == 69
    assert telemetry["waves"][-1]["probe_resume_pending_count"] == 1
    assert telemetry["waves"][-1]["candidate_results"][0]["probe_resume_pending"] is True


def test_parallel_and_serial_exact_candidate_results_match_on_toy_frontier(
    monkeypatch,
    tmp_path: Path,
) -> None:
    serial_root = _build_empty_frontier_project(tmp_path / "serial_match", width=2, height=2)
    parallel_root = _build_empty_frontier_project(tmp_path / "parallel_match", width=2, height=2)

    def fake_serial_benders(*, ghost_w: int, ghost_h: int, session=None, **kwargs):
        del session, kwargs
        if (int(ghost_w), int(ghost_h)) != (1, 1):
            fake_serial_benders.last_run_metadata = {
                "proof_summary": {"master_status": RUN_STATUS_INFEASIBLE},
                "exact_safe_cuts": [],
                "loaded_exact_safe_cut_count": 0,
                "generated_exact_safe_cut_count": 0,
            }
            return RUN_STATUS_INFEASIBLE, None
        fake_serial_benders.last_run_metadata = {
            "proof_summary": {"master_status": RUN_STATUS_CERTIFIED},
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        }
        return RUN_STATUS_CERTIFIED, {
            "ghost_pick": {
                "pose_idx": 0,
                "pose_id": "synthetic_pose_0",
                "anchor": {"x": 0, "y": 0},
                "facility_type": "synthetic",
            }
        }

    fake_serial_benders.last_run_metadata = {
        "proof_summary": {},
        "exact_safe_cuts": [],
        "loaded_exact_safe_cut_count": 0,
        "generated_exact_safe_cut_count": 0,
    }

    def fake_parallel_wave(*, pool, tasks):
        del pool
        results = []
        for task in reversed(tasks):
            if (int(task.candidate[1]), int(task.candidate[2])) != (1, 1):
                results.append(
                    WorkerResult(
                        dispatch_seq=task.dispatch_seq,
                        attempt_index=task.attempt_index,
                        candidate=task.candidate,
                        status=RUN_STATUS_INFEASIBLE,
                        solution=None,
                        proof_summary={"master_status": RUN_STATUS_INFEASIBLE},
                        exact_safe_cuts=[],
                        loaded_exact_safe_cut_count=0,
                        generated_exact_safe_cut_count=0,
                        worker_wall_seconds=0.01,
                        peak_rss_bytes=1,
                        error=None,
                    )
                )
            else:
                results.append(
                    WorkerResult(
                        dispatch_seq=task.dispatch_seq,
                        attempt_index=task.attempt_index,
                        candidate=task.candidate,
                        status=RUN_STATUS_CERTIFIED,
                        solution={
                            "ghost_pick": {
                                "pose_idx": 0,
                                "pose_id": "synthetic_pose_0",
                                "anchor": {"x": 0, "y": 0},
                                "facility_type": "synthetic",
                            }
                        },
                        proof_summary={"master_status": RUN_STATUS_CERTIFIED},
                        exact_safe_cuts=[],
                        loaded_exact_safe_cut_count=0,
                        generated_exact_safe_cut_count=0,
                        worker_wall_seconds=0.01,
                        peak_rss_bytes=1,
                        error=None,
                    )
                )
        return ParallelWaveExecution(
            completed=True,
            failure_reason=None,
            results=tuple(results),
            dispatched_candidate_keys=tuple(task.candidate_key for task in tasks),
            elapsed_seconds=0.02,
            peak_rss_bytes_external_total=2,
            peak_rss_bytes_internal_max_single_process=1,
        )

    monkeypatch.setattr(outer_search_module, "run_benders_for_ghost_rect", fake_serial_benders)
    monkeypatch.setattr(
        outer_search_module.ExactSearchSession,
        "create",
        staticmethod(lambda project_root, solve_mode="certified_exact": object()),
    )

    serial_status, serial_result = run_outer_search(
        project_root=serial_root,
        solve_mode="certified_exact",
        max_attempts=4,
        min_side=1,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
        parallel_processes=1,
    )

    monkeypatch.setattr(outer_search_module, "ExactParallelWorkerPool", _DummyParallelWorkerPool)
    monkeypatch.setattr(outer_search_module, "run_parallel_exact_campaign_wave", fake_parallel_wave)
    parallel_status, parallel_result = run_outer_search(
        project_root=parallel_root,
        solve_mode="certified_exact",
        max_attempts=4,
        min_side=1,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
        parallel_processes=2,
    )

    assert serial_status == parallel_status == RUN_STATUS_CERTIFIED
    assert serial_result is not None and parallel_result is not None
    assert serial_result["ghost_rect"] == parallel_result["ghost_rect"] == {"w": 1, "h": 1, "area": 1, "anchor_x": 0, "anchor_y": 0}

    serial_state = _read_campaign_state(serial_root)
    parallel_state = _read_campaign_state(parallel_root)
    assert serial_state["candidates"]["2x1"]["status"] == parallel_state["candidates"]["2x1"]["status"]
    assert serial_state["candidates"]["1x1"]["status"] == parallel_state["candidates"]["1x1"]["status"]


def test_parallel_wave_keeps_best_certified_result_under_out_of_order_completion(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_empty_frontier_project(tmp_path / "parallel_best_certified", width=6, height=6)
    expected_best: dict[str, dict[str, int]] = {}

    def fake_wave_executor(*, pool, tasks):
        assert isinstance(pool, _DummyParallelWorkerPool)
        # 权威全域的支配 frontier 从单头 (6,6) 起步, 头几波只有一个 head;
        # 单头波一律判 INFEASIBLE 削掉支配角, 等 frontier 裂成 ≥2 头的那一波
        # 再乱序回报两个 CERTIFIED, 专测乱序 merge 不丢 best。
        if len(tasks) < 2:
            return ParallelWaveExecution(
                completed=True,
                failure_reason=None,
                results=tuple(
                    WorkerResult(
                        dispatch_seq=task.dispatch_seq,
                        attempt_index=task.attempt_index,
                        candidate=task.candidate,
                        status=RUN_STATUS_INFEASIBLE,
                        solution=None,
                        proof_summary={"master_status": RUN_STATUS_INFEASIBLE},
                        exact_safe_cuts=[],
                        loaded_exact_safe_cut_count=0,
                        generated_exact_safe_cut_count=0,
                        worker_wall_seconds=0.01,
                        peak_rss_bytes=1,
                        error=None,
                    )
                    for task in tasks
                ),
                dispatched_candidate_keys=tuple(task.candidate_key for task in tasks),
                elapsed_seconds=0.02,
                peak_rss_bytes_external_total=2,
                peak_rss_bytes_internal_max_single_process=1,
            )
        # V82 oriented domain: equal-area transposed candidates (e.g. (6,5) and
        # (5,6)) can share a wave, so pick the wave's best by the same canonical
        # sort the campaign uses, not by bare area.
        sorted_tasks = sorted(
            tasks,
            key=lambda task: certified_frontier_module.candidate_sort_key(task.candidate),
        )
        big_task = sorted_tasks[0]
        small_task = sorted_tasks[-1]
        expected_best["ghost_rect"] = {
            "w": int(big_task.candidate[1]),
            "h": int(big_task.candidate[2]),
            "area": int(big_task.candidate[0]),
            "anchor_x": 0,
            "anchor_y": 0,
        }
        return ParallelWaveExecution(
            completed=True,
            failure_reason=None,
            results=(
                WorkerResult(
                    dispatch_seq=small_task.dispatch_seq,
                    attempt_index=small_task.attempt_index,
                    candidate=small_task.candidate,
                    status=RUN_STATUS_CERTIFIED,
                    solution={
                        # V84: terminal placement solutions may only carry
                        # mandatory instances and the ghost_pick marker.
                        "ghost_pick": {
                            "pose_idx": 0,
                            "pose_id": "synthetic_pose_0",
                            "facility_type": "synthetic",
                            "anchor": {"x": 0, "y": 0},
                        }
                    },
                    proof_summary={"master_status": RUN_STATUS_CERTIFIED},
                    exact_safe_cuts=[],
                    loaded_exact_safe_cut_count=0,
                    generated_exact_safe_cut_count=0,
                    worker_wall_seconds=0.01,
                    peak_rss_bytes=1,
                    error=None,
                ),
                WorkerResult(
                    dispatch_seq=big_task.dispatch_seq,
                    attempt_index=big_task.attempt_index,
                    candidate=big_task.candidate,
                    status=RUN_STATUS_CERTIFIED,
                    solution={
                        "ghost_pick": {
                            "pose_idx": 0,
                            "pose_id": "synthetic_pose_0",
                            "facility_type": "synthetic",
                            "anchor": {"x": 0, "y": 0},
                        }
                    },
                    proof_summary={"master_status": RUN_STATUS_CERTIFIED},
                    exact_safe_cuts=[],
                    loaded_exact_safe_cut_count=0,
                    generated_exact_safe_cut_count=0,
                    worker_wall_seconds=0.01,
                    peak_rss_bytes=1,
                    error=None,
                ),
            ),
            dispatched_candidate_keys=tuple(task.candidate_key for task in tasks),
            elapsed_seconds=0.02,
            peak_rss_bytes_external_total=2,
            peak_rss_bytes_internal_max_single_process=1,
        )

    monkeypatch.setattr(outer_search_module, "ExactParallelWorkerPool", _DummyParallelWorkerPool)
    monkeypatch.setattr(outer_search_module, "run_parallel_exact_campaign_wave", fake_wave_executor)

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        max_attempts=8,
        min_side=1,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
        parallel_processes=2,
    )

    state = _read_campaign_state(project_root)

    assert status == RUN_STATUS_CERTIFIED
    assert result is not None
    assert result["ghost_rect"] == expected_best["ghost_rect"]
    assert state["final_status"] == RUN_STATUS_CERTIFIED
    assert state["final_result"]["ghost_rect"] == expected_best["ghost_rect"]
    assert sum(1 for record in state["candidates"].values() if record["status"] == RUN_STATUS_CERTIFIED) >= 2


def test_worker_failure_preserves_certified_candidate_records_without_terminal_export(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_empty_frontier_project(tmp_path / "parallel_worker_failure_best", width=6, height=6)
    expected_best: dict[str, dict[str, int]] = {}

    def fake_wave_executor(*, pool, tasks):
        assert isinstance(pool, _DummyParallelWorkerPool)
        assert len(tasks) >= 2
        big_task = max(tasks, key=lambda task: int(task.candidate[0]))
        expected_best["ghost_rect"] = {
            "w": int(big_task.candidate[1]),
            "h": int(big_task.candidate[2]),
            "area": int(big_task.candidate[0]),
            "anchor_x": 0,
            "anchor_y": 0,
        }
        return ParallelWaveExecution(
            completed=False,
            failure_reason="worker_process_failed:pid=1:exitcode=1",
            results=(
                WorkerResult(
                    dispatch_seq=big_task.dispatch_seq,
                    attempt_index=big_task.attempt_index,
                    candidate=big_task.candidate,
                    status=RUN_STATUS_CERTIFIED,
                    solution={
                        "big_pick": {
                            "pose_idx": 0,
                            "pose_id": f"ghost_{int(big_task.candidate[1])}x{int(big_task.candidate[2])}",
                            "facility_type": "synthetic",
                            "anchor": {"x": 0, "y": 0},
                        }
                    },
                    proof_summary={"master_status": RUN_STATUS_CERTIFIED},
                    exact_safe_cuts=[],
                    loaded_exact_safe_cut_count=0,
                    generated_exact_safe_cut_count=0,
                    worker_wall_seconds=0.01,
                    peak_rss_bytes=1,
                    error=None,
                ),
            ),
            dispatched_candidate_keys=tuple(task.candidate_key for task in tasks),
            elapsed_seconds=0.02,
            peak_rss_bytes_external_total=2,
            peak_rss_bytes_internal_max_single_process=1,
        )

    monkeypatch.setattr(outer_search_module, "ExactParallelWorkerPool", _DummyParallelWorkerPool)
    monkeypatch.setattr(outer_search_module, "run_parallel_exact_campaign_wave", fake_wave_executor)

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        max_attempts=2,
        min_side=1,
        area_upper_bound=9,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
        parallel_processes=2,
    )

    state = _read_campaign_state(project_root)
    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)

    assert status == RUN_STATUS_UNKNOWN
    assert result is None
    assert state["final_status"] == RUN_STATUS_UNKNOWN
    assert state["last_stop_reason"]["reason"] == "worker_process_failed"
    assert state.get("final_result") is None
    assert resumed.resumed is True
    assert resumed.compatible_hashes is True
    candidate_key = f"{expected_best['ghost_rect']['w']}x{expected_best['ghost_rect']['h']}"
    assert state["candidates"][candidate_key]["status"] == RUN_STATUS_CERTIFIED
    assert resumed.best_certified_result() is None

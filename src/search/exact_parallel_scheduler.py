from __future__ import annotations

import multiprocessing as mp
import os
import queue
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import psutil

from src.runtime.process_priority import apply_process_priority_if_configured
from src.search.benders_loop import (
    DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    ExactSearchSession,
    create_exact_search_session,
    run_benders_for_ghost_rect,
)


@dataclass(frozen=True)
class WorkerTask:
    dispatch_seq: int
    attempt_index: int
    candidate: Tuple[int, int, int]
    master_seconds: float
    binding_seconds: float
    routing_seconds: float
    flow_seconds: float
    benders_max_iter: int
    disable_master_warm_start: bool
    preloaded_exact_safe_cuts: Tuple[Dict[str, Any], ...]

    @property
    def candidate_key(self) -> str:
        return f"{int(self.candidate[1])}x{int(self.candidate[2])}"


@dataclass(frozen=True)
class WorkerResult:
    dispatch_seq: int
    attempt_index: int
    candidate: Tuple[int, int, int]
    status: str
    solution: Optional[Dict[str, Any]]
    proof_summary: Dict[str, Any]
    exact_safe_cuts: List[Dict[str, Any]]
    loaded_exact_safe_cut_count: int
    generated_exact_safe_cut_count: int
    worker_wall_seconds: float
    peak_rss_bytes: int
    error: Optional[str]

    @property
    def candidate_key(self) -> str:
        return f"{int(self.candidate[1])}x{int(self.candidate[2])}"


@dataclass(frozen=True)
class ParallelWaveExecution:
    completed: bool
    failure_reason: Optional[str]
    results: Tuple[WorkerResult, ...]
    dispatched_candidate_keys: Tuple[str, ...]
    elapsed_seconds: float
    peak_rss_bytes_external_total: int
    peak_rss_bytes_internal_max_single_process: int
    heartbeat_events: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)


def build_parallel_worker_tasks(
    *,
    candidates: Sequence[Tuple[int, int, int]],
    attempt_start: int,
    attempt_indices: Optional[Sequence[int]] = None,
    master_seconds: float,
    binding_seconds: float,
    routing_seconds: float,
    flow_seconds: float,
    benders_max_iter: int,
    preloaded_cut_map: Mapping[str, Sequence[Mapping[str, Any]]],
    disable_master_warm_start: bool = False,
) -> List[WorkerTask]:
    tasks: List[WorkerTask] = []
    normalized_attempt_indices: Optional[List[int]] = None
    if attempt_indices is not None:
        normalized_attempt_indices = [int(value) for value in attempt_indices]
        if len(normalized_attempt_indices) != len(candidates):
            raise ValueError("attempt_indices length must match candidates length")
    for dispatch_seq, candidate in enumerate(candidates):
        candidate_key = f"{int(candidate[1])}x{int(candidate[2])}"
        raw_cuts = preloaded_cut_map.get(candidate_key, [])
        if normalized_attempt_indices is None:
            attempt_index = int(attempt_start + dispatch_seq + 1)
        else:
            attempt_index = int(normalized_attempt_indices[dispatch_seq])
        tasks.append(
            WorkerTask(
                dispatch_seq=int(dispatch_seq),
                attempt_index=attempt_index,
                candidate=(int(candidate[0]), int(candidate[1]), int(candidate[2])),
                master_seconds=float(master_seconds),
                binding_seconds=float(binding_seconds),
                routing_seconds=float(routing_seconds),
                flow_seconds=float(flow_seconds),
                benders_max_iter=int(benders_max_iter),
                disable_master_warm_start=bool(disable_master_warm_start),
                preloaded_exact_safe_cuts=tuple(dict(raw_cut) for raw_cut in raw_cuts),
            )
        )
    return tasks


def _rss_bytes(process: psutil.Process) -> int:
    try:
        return int(process.memory_info().rss)
    except Exception:
        return 0


def _worker_entry(
    *,
    worker_index: int,
    project_root: str,
    solve_mode: str,
    master_search_profile: str,
    task_queue: Any,
    result_queue: Any,
) -> None:
    process = psutil.Process(os.getpid())
    peak_rss_bytes = _rss_bytes(process)
    priority_info = apply_process_priority_if_configured()
    try:
        session = create_exact_search_session(
            Path(project_root),
            solve_mode=solve_mode,
            master_search_profile=master_search_profile,
        )
        peak_rss_bytes = max(peak_rss_bytes, _rss_bytes(process))
        result_queue.put(
            {
                "message_type": "READY",
                "worker_index": int(worker_index),
                "core_build_seconds": float(session.core_build_seconds),
                "peak_rss_bytes": int(peak_rss_bytes),
                "process_priority": dict(priority_info),
            }
        )
    except Exception as exc:
        result_queue.put(
            {
                "message_type": "STARTUP_ERROR",
                "worker_index": int(worker_index),
                "error": f"{type(exc).__name__}: {exc}",
                "process_priority": dict(priority_info),
            }
        )
        return

    while True:
        task = task_queue.get()
        if task is None:
            return
        started = time.perf_counter()
        peak_rss_bytes = max(peak_rss_bytes, _rss_bytes(process))
        try:
            _area, ghost_w, ghost_h = task.candidate

            def _emit_worker_heartbeat(payload: Mapping[str, Any]) -> None:
                result_queue.put(
                    {
                        "message_type": "HEARTBEAT",
                        "worker_index": int(worker_index),
                        "dispatch_seq": int(task.dispatch_seq),
                        "attempt_index": int(task.attempt_index),
                        "candidate": (
                            int(task.candidate[0]),
                            int(task.candidate[1]),
                            int(task.candidate[2]),
                        ),
                        "candidate_key": task.candidate_key,
                        "payload": dict(payload),
                    }
                )

            status, solution = run_benders_for_ghost_rect(
                ghost_w=int(ghost_w),
                ghost_h=int(ghost_h),
                max_iterations=int(task.benders_max_iter),
                project_root=Path(project_root),
                solve_mode=solve_mode,
                master_seconds=float(task.master_seconds),
                binding_seconds=float(task.binding_seconds),
                routing_seconds=float(task.routing_seconds),
                flow_seconds=float(task.flow_seconds),
                campaign=None,
                session=session,
                preloaded_exact_safe_cuts=list(task.preloaded_exact_safe_cuts),
                master_search_profile=master_search_profile,
                disable_master_warm_start=bool(task.disable_master_warm_start),
                heartbeat_callback=_emit_worker_heartbeat,
            )
            metadata = dict(getattr(run_benders_for_ghost_rect, "last_run_metadata", {}) or {})
            peak_rss_bytes = max(peak_rss_bytes, _rss_bytes(process))
            worker_result = WorkerResult(
                dispatch_seq=int(task.dispatch_seq),
                attempt_index=int(task.attempt_index),
                candidate=(int(task.candidate[0]), int(task.candidate[1]), int(task.candidate[2])),
                status=str(status),
                solution=None if solution is None else dict(solution),
                proof_summary=dict(metadata.get("proof_summary", {})),
                exact_safe_cuts=[dict(raw_cut) for raw_cut in metadata.get("exact_safe_cuts", [])],
                loaded_exact_safe_cut_count=int(metadata.get("loaded_exact_safe_cut_count", 0)),
                generated_exact_safe_cut_count=int(metadata.get("generated_exact_safe_cut_count", 0)),
                worker_wall_seconds=float(time.perf_counter() - started),
                peak_rss_bytes=int(peak_rss_bytes),
                error=None,
            )
        except Exception as exc:
            peak_rss_bytes = max(peak_rss_bytes, _rss_bytes(process))
            worker_result = WorkerResult(
                dispatch_seq=int(task.dispatch_seq),
                attempt_index=int(task.attempt_index),
                candidate=(int(task.candidate[0]), int(task.candidate[1]), int(task.candidate[2])),
                status="UNKNOWN",
                solution=None,
                proof_summary={},
                exact_safe_cuts=[],
                loaded_exact_safe_cut_count=0,
                generated_exact_safe_cut_count=0,
                worker_wall_seconds=float(time.perf_counter() - started),
                peak_rss_bytes=int(peak_rss_bytes),
                error=f"{type(exc).__name__}: {exc}",
            )
        result_queue.put({"message_type": "RESULT", "result": worker_result})
        if worker_result.error is not None:
            return


class ExactParallelWorkerPool:
    def __init__(
        self,
        *,
        process_count: int,
        project_root: Path,
        solve_mode: str = "certified_exact",
        master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
        rss_sample_interval_seconds: float = 0.25,
    ) -> None:
        self.process_count = int(process_count)
        self.project_root = Path(project_root).resolve()
        self.solve_mode = str(solve_mode)
        self.master_search_profile = str(master_search_profile)
        self.rss_sample_interval_seconds = float(rss_sample_interval_seconds)
        self._ctx = mp.get_context("spawn")
        self._task_queue = self._ctx.Queue()
        self._result_queue = self._ctx.Queue()
        self._processes: List[mp.Process] = []
        self._worker_priority_reports: List[Dict[str, Any]] = []
        self._started = False
        self._closed = False
        self._total_crash_respawns = 0

    def _sum_process_tree_rss(self) -> int:
        total_bytes = 0
        for process in self._processes:
            if process.pid is None:
                continue
            try:
                ps_process = psutil.Process(process.pid)
                total_bytes += _rss_bytes(ps_process)
                for child in ps_process.children(recursive=True):
                    total_bytes += _rss_bytes(child)
            except Exception:
                continue
        return int(total_bytes)

    def _drain_result_queue(self) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = []
        while True:
            try:
                messages.append(self._result_queue.get_nowait())
            except queue.Empty:
                break
        return messages

    def _respawn_all_workers(self) -> None:
        for process in self._processes:
            if process.is_alive():
                try:
                    self._task_queue.put_nowait(None)
                except Exception:
                    pass
        for process in self._processes:
            process.join(timeout=3.0)
            if process.is_alive():
                process.terminate()
                process.join(timeout=5.0)
        self._task_queue = self._ctx.Queue()
        self._result_queue = self._ctx.Queue()
        self._processes = []
        self._started = False
        self._closed = False
        self.start()

    def start(self) -> None:
        if self._started:
            return
        ready_workers = 0
        for worker_index in range(self.process_count):
            process = self._ctx.Process(
                target=_worker_entry,
                kwargs={
                    "worker_index": int(worker_index),
                    "project_root": str(self.project_root),
                    "solve_mode": self.solve_mode,
                    "master_search_profile": self.master_search_profile,
                    "task_queue": self._task_queue,
                    "result_queue": self._result_queue,
                },
            )
            process.start()
            self._processes.append(process)

        while ready_workers < self.process_count:
            try:
                message = self._result_queue.get(timeout=self.rss_sample_interval_seconds)
            except queue.Empty:
                for process in self._processes:
                    if process.exitcode not in (None, 0):
                        raise RuntimeError(
                            f"parallel_worker_startup_failed:pid={process.pid}:exitcode={process.exitcode}"
                        )
                continue
            message_type = str(message.get("message_type", ""))
            if message_type == "READY":
                self._worker_priority_reports.append(dict(message.get("process_priority", {})))
                ready_workers += 1
                continue
            if message_type == "STARTUP_ERROR":
                self.terminate()
                raise RuntimeError(str(message.get("error", "parallel_worker_startup_error")))
        self._started = True

    def run_wave(
        self,
        tasks: Sequence[WorkerTask],
        *,
        max_crash_respawns: int = 2,
    ) -> ParallelWaveExecution:
        if self._closed:
            raise RuntimeError("parallel worker pool is already closed")
        if not tasks:
            return ParallelWaveExecution(
                completed=True,
                failure_reason=None,
                results=tuple(),
                dispatched_candidate_keys=tuple(),
                elapsed_seconds=0.0,
                peak_rss_bytes_external_total=0,
                peak_rss_bytes_internal_max_single_process=0,
            )
        self.start()

        started = time.perf_counter()
        for task in tasks:
            self._task_queue.put(task)

        results_by_seq: Dict[int, WorkerResult] = {}
        failure_reason: Optional[str] = None
        peak_rss_total_bytes = 0
        heartbeat_events: List[Dict[str, Any]] = []
        wave_crash_respawns = 0

        while len(results_by_seq) < len(tasks):
            peak_rss_total_bytes = max(peak_rss_total_bytes, self._sum_process_tree_rss())
            try:
                message = self._result_queue.get(timeout=self.rss_sample_interval_seconds)
            except queue.Empty:
                any_crashed = any(
                    p.exitcode not in (None, 0) for p in self._processes
                )
                if any_crashed:
                    for msg in self._drain_result_queue():
                        msg_type = str(msg.get("message_type", ""))
                        if msg_type == "HEARTBEAT":
                            heartbeat_events.append(_normalize_heartbeat_message(msg))
                        elif msg_type == "RESULT":
                            r = msg.get("result")
                            if isinstance(r, WorkerResult):
                                results_by_seq.setdefault(int(r.dispatch_seq), r)
                    pending = [t for t in tasks if t.dispatch_seq not in results_by_seq]
                    if not pending:
                        break
                    if wave_crash_respawns >= max_crash_respawns:
                        failure_reason = (
                            f"worker_crash_respawn_limit:{wave_crash_respawns}:"
                            + ":".join(
                                f"pid={p.pid}:exit={p.exitcode}"
                                for p in self._processes
                                if p.exitcode not in (None, 0)
                            )
                        )
                        break
                    self._respawn_all_workers()
                    for task in pending:
                        self._task_queue.put(task)
                    wave_crash_respawns += 1
                    self._total_crash_respawns += 1
                continue

            message_type = str(message.get("message_type", ""))
            if message_type == "HEARTBEAT":
                heartbeat_events.append(_normalize_heartbeat_message(message))
                continue
            if message_type != "RESULT":
                continue

            result = message.get("result")
            if not isinstance(result, WorkerResult):
                failure_reason = "worker_result_invalid"
                break
            results_by_seq[int(result.dispatch_seq)] = result
            if result.error is not None and failure_reason is None:
                failure_reason = str(result.error)
                break

        while True:
            peak_rss_total_bytes = max(peak_rss_total_bytes, self._sum_process_tree_rss())
            try:
                message = self._result_queue.get_nowait()
            except queue.Empty:
                break
            message_type = str(message.get("message_type", ""))
            if message_type == "HEARTBEAT":
                heartbeat_events.append(_normalize_heartbeat_message(message))
                continue
            if message_type != "RESULT":
                continue
            result = message.get("result")
            if isinstance(result, WorkerResult):
                results_by_seq.setdefault(int(result.dispatch_seq), result)

        if failure_reason is not None:
            self.terminate()
        else:
            self._respawn_all_workers()

        sorted_results = tuple(
            results_by_seq[dispatch_seq] for dispatch_seq in sorted(results_by_seq.keys())
        )
        return ParallelWaveExecution(
            completed=(
                failure_reason is None
                and len(sorted_results) == len(tasks)
                and all(result.error is None for result in sorted_results)
            ),
            failure_reason=failure_reason,
            results=sorted_results,
            dispatched_candidate_keys=tuple(task.candidate_key for task in tasks),
            elapsed_seconds=float(time.perf_counter() - started),
            peak_rss_bytes_external_total=int(peak_rss_total_bytes),
            peak_rss_bytes_internal_max_single_process=max(
                [int(result.peak_rss_bytes) for result in sorted_results],
                default=0,
            ),
            heartbeat_events=tuple(heartbeat_events),
        )

    def close(self) -> None:
        if self._closed:
            return
        for _process in self._processes:
            self._task_queue.put(None)
        for process in self._processes:
            process.join(timeout=5.0)
            if process.is_alive():
                process.terminate()
                process.join(timeout=5.0)
        self._closed = True

    def terminate(self) -> None:
        if self._closed:
            return
        for process in self._processes:
            if process.is_alive():
                process.terminate()
        for process in self._processes:
            process.join(timeout=5.0)
        self._closed = True

    def __enter__(self) -> "ExactParallelWorkerPool":
        self.start()
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> None:
        if exc_type is None:
            self.close()
        else:
            self.terminate()


def run_parallel_exact_campaign_wave(
    *,
    pool: ExactParallelWorkerPool,
    tasks: Sequence[WorkerTask],
) -> ParallelWaveExecution:
    return pool.run_wave(tasks)


def _normalize_heartbeat_message(message: Mapping[str, Any]) -> Dict[str, Any]:
    payload = message.get("payload")
    return {
        "message_type": "HEARTBEAT",
        "worker_index": int(message.get("worker_index", -1)),
        "dispatch_seq": int(message.get("dispatch_seq", -1)),
        "attempt_index": int(message.get("attempt_index", -1)),
        "candidate": [
            int(value) for value in tuple(message.get("candidate", (0, 0, 0)))
        ],
        "candidate_key": str(message.get("candidate_key", "")),
        "payload": dict(payload) if isinstance(payload, Mapping) else {},
    }

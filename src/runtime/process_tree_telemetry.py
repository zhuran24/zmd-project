from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Iterable

import psutil


class ProcessTreeSampler:
    def __init__(self, root_pid: int | None = None) -> None:
        self.root_pid = int(os.getpid() if root_pid is None else root_pid)
        self._process_cache: dict[int, psutil.Process] = {}

    def sample(self) -> dict[str, Any]:
        processes = [_process_snapshot(process) for process in self._iter_processes()]
        return {
            "schema": "phase3b-process-tree-telemetry-sample/v0",
            "sample_time_unix": time.time(),
            "root_pid": self.root_pid,
            "processes": processes,
            "aggregate": _aggregate(processes),
        }

    def _iter_processes(self) -> list[psutil.Process]:
        try:
            root = self._cached_process(self.root_pid)
            processes = [root]
            processes.extend(root.children(recursive=True))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError):
            return []
        cached: list[psutil.Process] = []
        seen: set[int] = set()
        for process in processes:
            if int(process.pid) in seen:
                continue
            seen.add(int(process.pid))
            cached.append(self._cached_process(int(process.pid)))
        return cached

    def _cached_process(self, pid: int) -> psutil.Process:
        if pid not in self._process_cache:
            self._process_cache[pid] = psutil.Process(pid)
        return self._process_cache[pid]


def sample_process_tree(root_pid: int | None = None) -> dict[str, Any]:
    return ProcessTreeSampler(root_pid).sample()


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("a", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
        handle.write("\n")


def summarize_telemetry_samples(samples: Iterable[dict[str, Any]]) -> dict[str, Any]:
    sample_list = [sample for sample in samples if isinstance(sample, dict)]
    if not sample_list:
        return {
            "sample_count": 0,
            "peak_process_count": 0,
            "peak_thread_count": 0,
            "peak_total_rss_bytes": 0,
            "peak_total_private_bytes": 0,
            "peak_total_cpu_percent": 0.0,
        }
    aggregates = [
        sample.get("aggregate", {}) for sample in sample_list if isinstance(sample.get("aggregate"), dict)
    ]
    return {
        "sample_count": len(sample_list),
        "peak_process_count": max((int(agg.get("process_count", 0)) for agg in aggregates), default=0),
        "peak_thread_count": max((int(agg.get("thread_count", 0)) for agg in aggregates), default=0),
        "peak_total_rss_bytes": max((int(agg.get("total_rss_bytes", 0)) for agg in aggregates), default=0),
        "peak_total_private_bytes": max(
            (int(agg.get("total_private_bytes", 0)) for agg in aggregates),
            default=0,
        ),
        "peak_total_cpu_percent": max(
            (float(agg.get("total_cpu_percent", 0.0)) for agg in aggregates),
            default=0.0,
        ),
    }


def read_telemetry_jsonl(path: Path) -> list[dict[str, Any]]:
    if not Path(path).exists():
        return []
    samples: list[dict[str, Any]] = []
    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            samples.append(payload)
    return samples


def _process_snapshot(process: psutil.Process) -> dict[str, Any]:
    try:
        with process.oneshot():
            memory = _memory_snapshot(process)
            return {
                "pid": int(process.pid),
                "ppid": _safe_call(process, "ppid", default=None),
                "name": _safe_call(process, "name", default=None),
                "status": _safe_call(process, "status", default=None),
                "create_time": _safe_call(process, "create_time", default=None),
                "num_threads": int(_safe_call(process, "num_threads", default=0) or 0),
                "cpu_percent": float(_safe_call(process, "cpu_percent", default=0.0) or 0.0),
                "nice": _safe_call(process, "nice", default=None),
                "cpu_affinity": _safe_call(process, "cpu_affinity", default=None),
                "memory": memory,
                "io": _io_snapshot(process),
            }
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as exc:
        return {
            "pid": int(getattr(process, "pid", -1)),
            "error": f"{type(exc).__name__}: {exc}",
            "num_threads": 0,
            "cpu_percent": 0.0,
            "memory": {"rss_bytes": 0, "vms_bytes": 0, "private_bytes": 0},
        }


def _memory_snapshot(process: psutil.Process) -> dict[str, int | None]:
    try:
        memory = process.memory_info()
        result: dict[str, int | None] = {
            "rss_bytes": int(getattr(memory, "rss", 0)),
            "vms_bytes": int(getattr(memory, "vms", 0)),
            "private_bytes": None,
        }
        try:
            full = process.memory_full_info()
            private = getattr(full, "private", None)
            if private is not None:
                result["private_bytes"] = int(private)
        except Exception:
            pass
        return result
    except Exception:
        return {"rss_bytes": 0, "vms_bytes": 0, "private_bytes": None}


def _io_snapshot(process: psutil.Process) -> dict[str, int] | None:
    try:
        counters = process.io_counters()
        return {
            "read_count": int(getattr(counters, "read_count", 0)),
            "write_count": int(getattr(counters, "write_count", 0)),
            "read_bytes": int(getattr(counters, "read_bytes", 0)),
            "write_bytes": int(getattr(counters, "write_bytes", 0)),
        }
    except Exception:
        return None


def _aggregate(processes: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "process_count": len(processes),
        "pids": [int(process.get("pid")) for process in processes if process.get("pid") is not None],
        "thread_count": sum(int(process.get("num_threads", 0) or 0) for process in processes),
        "total_cpu_percent": sum(float(process.get("cpu_percent", 0.0) or 0.0) for process in processes),
        "total_rss_bytes": sum(
            int(_memory(process).get("rss_bytes", 0) or 0) for process in processes
        ),
        "total_private_bytes": sum(
            int(_memory(process).get("private_bytes", 0) or 0) for process in processes
        ),
    }


def _memory(process: dict[str, Any]) -> dict[str, Any]:
    memory = process.get("memory")
    return memory if isinstance(memory, dict) else {}


def _safe_call(process: psutil.Process, method_name: str, *, default: Any) -> Any:
    try:
        method = getattr(process, method_name)
        return method()
    except Exception:
        return default

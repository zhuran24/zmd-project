from __future__ import annotations

import multiprocessing
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

import psutil

from src.runtime.process_priority import PROCESS_PRIORITY_ENV

CP_SAT_WORKER_ENV_VARS = (
    "EXACT_CP_SAT_WORKERS",
    "EXACT_MASTER_CP_SAT_WORKERS",
    "EXACT_LOCAL_CAPACITY_CP_SAT_WORKERS",
    "EXACT_BINDING_CP_SAT_WORKERS",
    "EXACT_ROUTING_CP_SAT_WORKERS",
)

TUNING_ENV_VARS = (
    *CP_SAT_WORKER_ENV_VARS,
    PROCESS_PRIORITY_ENV,
    "PYTHONPATH",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
)


def build_hardware_profile(
    project_root: Path | None = None,
    *,
    drives: Iterable[str] = ("C", "D", "E"),
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env_map = os.environ if env is None else env
    current_process = psutil.Process(os.getpid())
    return {
        "schema": "phase3b-local-hardware-profile/v0",
        "project_root": str(Path(project_root).resolve()) if project_root is not None else None,
        "platform": _platform_snapshot(),
        "python": _python_snapshot(),
        "ortools": _ortools_snapshot(),
        "cpu": _cpu_snapshot(current_process),
        "memory": _memory_snapshot(),
        "process": _process_snapshot(current_process),
        "environment": {
            "vars": {name: env_map.get(name) for name in TUNING_ENV_VARS},
            "cp_sat_worker_env_vars": list(CP_SAT_WORKER_ENV_VARS),
        },
        "disk": {
            "drives": {
                str(drive).upper().rstrip(":"): _drive_snapshot(str(drive))
                for drive in drives
            }
        },
        "safety": {
            "profile_is_observability_only": True,
            "final_168h_started": False,
            "checkpoint_written": False,
            "proof_source_mutated": False,
            "release_viewer_frontdoor_promoted": False,
        },
    }


def _platform_snapshot() -> dict[str, Any]:
    return {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "platform": platform.platform(),
    }


def _python_snapshot() -> dict[str, Any]:
    return {
        "version": sys.version,
        "version_info": {
            "major": sys.version_info.major,
            "minor": sys.version_info.minor,
            "micro": sys.version_info.micro,
        },
        "executable": sys.executable,
        "implementation": platform.python_implementation(),
    }


def _ortools_snapshot() -> dict[str, Any]:
    try:
        import ortools  # type: ignore

        return {"available": True, "version": getattr(ortools, "__version__", None)}
    except Exception as exc:
        return {
            "available": False,
            "version": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _cpu_snapshot(process: psutil.Process) -> dict[str, Any]:
    return {
        "logical_count": os.cpu_count(),
        "physical_count": psutil.cpu_count(logical=False),
        "multiprocessing_count": multiprocessing.cpu_count(),
        "frequency": _as_dict_or_error(psutil.cpu_freq),
        "affinity": _safe_process_call(process, "cpu_affinity"),
    }


def _memory_snapshot() -> dict[str, Any]:
    virtual = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return {
        "virtual": {
            "total_bytes": int(virtual.total),
            "available_bytes": int(virtual.available),
            "used_bytes": int(virtual.used),
            "percent": float(virtual.percent),
        },
        "swap": {
            "total_bytes": int(swap.total),
            "used_bytes": int(swap.used),
            "free_bytes": int(swap.free),
            "percent": float(swap.percent),
        },
    }


def _process_snapshot(process: psutil.Process) -> dict[str, Any]:
    return {
        "pid": int(process.pid),
        "name": _safe_process_call(process, "name"),
        "status": _safe_process_call(process, "status"),
        "nice": _safe_process_call(process, "nice"),
        "num_threads": _safe_process_call(process, "num_threads"),
        "cwd": _safe_process_call(process, "cwd"),
        "cpu_affinity": _safe_process_call(process, "cpu_affinity"),
    }


def _drive_snapshot(drive: str) -> dict[str, Any]:
    drive_name = str(drive).upper().rstrip(":")
    root = Path(f"{drive_name}:\\")
    if not root.exists():
        return {"root": str(root), "exists": False}
    try:
        usage = shutil.disk_usage(root)
        return {
            "root": str(root),
            "exists": True,
            "total_bytes": int(usage.total),
            "used_bytes": int(usage.used),
            "free_bytes": int(usage.free),
            "free_gib": round(float(usage.free) / (1024 ** 3), 3),
        }
    except Exception as exc:
        return {
            "root": str(root),
            "exists": True,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _as_dict_or_error(callable_obj: Any) -> dict[str, Any]:
    try:
        value = callable_obj()
        if value is None:
            return {"available": False, "value": None}
        if hasattr(value, "_asdict"):
            return {"available": True, "value": dict(value._asdict())}
        return {"available": True, "value": value}
    except Exception as exc:
        return {"available": False, "error": f"{type(exc).__name__}: {exc}"}


def _safe_process_call(process: psutil.Process, method_name: str) -> Any:
    try:
        method = getattr(process, method_name)
        return method()
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}

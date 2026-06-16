from __future__ import annotations

import os
import platform
import json
import subprocess
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import psutil

from src.runtime.process_priority import _is_windows_process_priority_supported


def build_cpu_topology_snapshot(
    project_root: Path | None = None,
    *,
    process: psutil.Process | None = None,
    logical_count: int | None = None,
    physical_count: int | None = None,
    windows_processor_info: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    current_process = process or psutil.Process(os.getpid())
    resolved_logical_count = int(logical_count or os.cpu_count() or 0)
    resolved_physical_count = physical_count
    if resolved_physical_count is None:
        resolved_physical_count = psutil.cpu_count(logical=False)
    current_affinity = _safe_process_call(current_process, "cpu_affinity")
    if not isinstance(current_affinity, list):
        current_affinity = list(range(resolved_logical_count))
    logical_processors = [
        {
            "logical_id": logical_id,
            "selected_by_current_affinity": logical_id in set(current_affinity),
            "core_type": None,
            "core_type_source": None,
        }
        for logical_id in range(resolved_logical_count)
    ]
    return {
        "schema": "phase3b-cpu-topology-snapshot/v0",
        "project_root": str(Path(project_root).resolve()) if project_root is not None else None,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        },
        "cpu": {
            "logical_processor_count": resolved_logical_count,
            "physical_core_count": resolved_physical_count,
            "cpu_frequency": _as_dict_or_error(psutil.cpu_freq),
            "windows_processor": dict(windows_processor_info)
            if windows_processor_info is not None
            else _windows_processor_snapshot(),
            "logical_processors": logical_processors,
        },
        "process": {
            "pid": int(current_process.pid),
            "current_affinity": current_affinity,
            "current_affinity_mask_hex": affinity_mask_hex(current_affinity),
        },
        "priority": {
            "supported": bool(_is_windows_process_priority_supported()),
            "supported_modes": ["normal", "high"],
        },
        "pe_mapping": {
            "confidence": "unverified",
            "source": None,
            "reason": "No trusted P/E core type source was recorded for logical processor ids.",
            "can_drive_medium_confirmation": False,
        },
        "safety": {
            "observability_only": True,
            "proof_source": False,
            "checkpoint_written": False,
            "production_profile_changed": False,
        },
    }


def affinity_mask_hex(logical_ids: Iterable[int]) -> str:
    mask = 0
    for logical_id in sorted({int(value) for value in logical_ids if int(value) >= 0}):
        mask |= 1 << logical_id
    return hex(mask)


def reserve_highest_logical_ids(
    logical_ids: Sequence[int],
    reserve_count: int,
) -> dict[str, Any]:
    unique_ids = sorted({int(value) for value in logical_ids})
    reserve_count = max(0, min(int(reserve_count), len(unique_ids)))
    reserved = unique_ids[-reserve_count:] if reserve_count else []
    allowed = [logical_id for logical_id in unique_ids if logical_id not in set(reserved)]
    return {
        "allowed_logical_ids": allowed,
        "reserved_logical_ids": reserved,
        "allowed_affinity_mask_hex": affinity_mask_hex(allowed),
        "reserved_affinity_mask_hex": affinity_mask_hex(reserved),
    }


def disjoint_process_groups(
    logical_ids: Sequence[int],
    process_count: int,
) -> list[dict[str, Any]]:
    unique_ids = sorted({int(value) for value in logical_ids})
    count = max(1, int(process_count))
    groups: list[list[int]] = [[] for _ in range(count)]
    for index, logical_id in enumerate(unique_ids):
        groups[index % count].append(logical_id)
    return [
        {
            "process_index": index,
            "logical_ids": group,
            "affinity_mask_hex": affinity_mask_hex(group),
        }
        for index, group in enumerate(groups)
    ]


def _windows_processor_snapshot() -> dict[str, Any]:
    if os.name != "nt":
        return {"available": False, "reason": "non_windows_platform"}
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        (
            "Get-CimInstance Win32_Processor | "
            "Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,ThreadCount,"
            "MaxClockSpeed,CurrentClockSpeed,L2CacheSize,L3CacheSize | "
            "ConvertTo-Json -Compress"
        ),
    ]
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception as exc:
        return {"available": False, "error": f"{type(exc).__name__}: {exc}"}
    if result.returncode != 0:
        return {
            "available": False,
            "error": (result.stderr or result.stdout or "").strip(),
            "return_code": int(result.returncode),
        }
    raw_json = result.stdout.strip()
    try:
        payload = json.loads(raw_json)
    except Exception:
        return {
            "available": True,
            "raw_json": raw_json,
            "parse_error": "json_decode_failed",
        }
    return {
        "available": True,
        "processors": payload if isinstance(payload, list) else [payload],
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

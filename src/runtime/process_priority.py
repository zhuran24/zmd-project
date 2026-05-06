from __future__ import annotations

import os
import sys
from typing import Any, Dict, Optional, Tuple

import psutil

PROCESS_PRIORITY_ENV = "EXACT_PROCESS_PRIORITY"
PROCESS_PRIORITY_MODE_NORMAL = "normal"
PROCESS_PRIORITY_MODE_HIGH = "high"

_SUPPORTED_PRIORITY_MODES = {
    PROCESS_PRIORITY_MODE_NORMAL,
    PROCESS_PRIORITY_MODE_HIGH,
}
_LAST_PRIORITY_APPLICATION: Dict[str, Any] = {
    "pid": None,
    "mode": None,
    "source": None,
    "result": None,
}


def _normalize_process_priority_mode(raw_mode: Optional[str], *, source_name: str) -> Optional[str]:
    if raw_mode is None:
        return None
    mode = str(raw_mode).strip().lower()
    if not mode:
        return None
    if mode not in _SUPPORTED_PRIORITY_MODES:
        raise ValueError(
            f"{source_name} must be one of: {', '.join(sorted(_SUPPORTED_PRIORITY_MODES))}"
        )
    return str(mode)


def _resolve_process_priority_mode_and_source(cli_value: Optional[str] = None) -> Tuple[str, str]:
    cli_mode = _normalize_process_priority_mode(cli_value, source_name="process priority CLI")
    if cli_mode is not None:
        return str(cli_mode), "cli"
    env_mode = _normalize_process_priority_mode(
        os.getenv(PROCESS_PRIORITY_ENV),
        source_name=PROCESS_PRIORITY_ENV,
    )
    if env_mode is not None:
        return str(env_mode), "env"
    return PROCESS_PRIORITY_MODE_NORMAL, "default"


def resolve_process_priority_mode(cli_value: Optional[str] = None) -> str:
    mode, _source = _resolve_process_priority_mode_and_source(cli_value)
    return str(mode)


def configure_process_priority_env(mode: str) -> str:
    normalized_mode = _normalize_process_priority_mode(mode, source_name="process priority CLI")
    if normalized_mode is None:  # pragma: no cover - defensive branch.
        raise ValueError("process priority mode cannot be empty")
    os.environ[PROCESS_PRIORITY_ENV] = str(normalized_mode)
    return str(normalized_mode)


def _is_windows_process_priority_supported() -> bool:
    return os.name == "nt" and hasattr(psutil, "NORMAL_PRIORITY_CLASS") and hasattr(
        psutil,
        "HIGH_PRIORITY_CLASS",
    )


def _priority_class_for_mode(mode: str) -> int:
    if mode == PROCESS_PRIORITY_MODE_NORMAL:
        return int(psutil.NORMAL_PRIORITY_CLASS)
    if mode == PROCESS_PRIORITY_MODE_HIGH:
        return int(psutil.HIGH_PRIORITY_CLASS)
    raise ValueError(f"Unsupported process priority mode: {mode}")


def apply_process_priority_if_configured(cli_value: Optional[str] = None) -> Dict[str, Any]:
    pid = int(os.getpid())
    platform = str(sys.platform)
    try:
        mode, source = _resolve_process_priority_mode_and_source(cli_value)
    except Exception as exc:
        return {
            "mode": "invalid",
            "source": "invalid",
            "applied": False,
            "error": f"{type(exc).__name__}: {exc}",
            "platform": platform,
        }

    cached_result = _LAST_PRIORITY_APPLICATION.get("result")
    if (
        _LAST_PRIORITY_APPLICATION.get("pid") == pid
        and _LAST_PRIORITY_APPLICATION.get("mode") == mode
        and _LAST_PRIORITY_APPLICATION.get("source") == source
        and isinstance(cached_result, dict)
    ):
        return dict(cached_result)

    if source == "default":
        result = {
            "mode": str(mode),
            "source": str(source),
            "applied": False,
            "error": None,
            "platform": platform,
        }
    elif not _is_windows_process_priority_supported():
        result = {
            "mode": str(mode),
            "source": str(source),
            "applied": False,
            "error": f"unsupported_platform:{platform}",
            "platform": platform,
        }
    else:
        try:
            psutil.Process(pid).nice(_priority_class_for_mode(str(mode)))
            result = {
                "mode": str(mode),
                "source": str(source),
                "applied": True,
                "error": None,
                "platform": platform,
            }
        except Exception as exc:
            result = {
                "mode": str(mode),
                "source": str(source),
                "applied": False,
                "error": f"{type(exc).__name__}: {exc}",
                "platform": platform,
            }

    _LAST_PRIORITY_APPLICATION["pid"] = pid
    _LAST_PRIORITY_APPLICATION["mode"] = str(mode)
    _LAST_PRIORITY_APPLICATION["source"] = str(source)
    _LAST_PRIORITY_APPLICATION["result"] = dict(result)
    return dict(result)

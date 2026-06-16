from __future__ import annotations

import os

import src.runtime.process_priority as process_priority_module
from src.runtime.process_priority import (
    PROCESS_PRIORITY_ENV,
    PROCESS_PRIORITY_MODE_HIGH,
    PROCESS_PRIORITY_MODE_NORMAL,
    apply_process_priority_if_configured,
    configure_process_priority_env,
    resolve_process_priority_mode,
)


def _reset_priority_cache() -> None:
    process_priority_module._LAST_PRIORITY_APPLICATION.update(
        {"pid": None, "mode": None, "source": None, "result": None}
    )


def test_resolve_process_priority_mode_defaults_to_normal(monkeypatch) -> None:
    monkeypatch.delenv(PROCESS_PRIORITY_ENV, raising=False)
    _reset_priority_cache()

    assert resolve_process_priority_mode() == PROCESS_PRIORITY_MODE_NORMAL
    result = apply_process_priority_if_configured()
    assert result["mode"] == PROCESS_PRIORITY_MODE_NORMAL
    assert result["source"] == "default"
    assert result["applied"] is False
    assert result["error"] is None


def test_resolve_process_priority_mode_reads_env_high(monkeypatch) -> None:
    monkeypatch.setenv(PROCESS_PRIORITY_ENV, PROCESS_PRIORITY_MODE_HIGH)
    _reset_priority_cache()

    assert resolve_process_priority_mode() == PROCESS_PRIORITY_MODE_HIGH
    assert resolve_process_priority_mode("normal") == PROCESS_PRIORITY_MODE_NORMAL


def test_configure_process_priority_env_sets_explicit_override(monkeypatch) -> None:
    monkeypatch.delenv(PROCESS_PRIORITY_ENV, raising=False)

    configured = configure_process_priority_env(PROCESS_PRIORITY_MODE_HIGH)

    assert configured == PROCESS_PRIORITY_MODE_HIGH
    assert os.getenv(PROCESS_PRIORITY_ENV) == PROCESS_PRIORITY_MODE_HIGH


def test_apply_process_priority_uses_windows_high_priority_class(monkeypatch) -> None:
    calls: dict[str, int] = {}

    class _FakeProcess:
        def __init__(self, pid: int) -> None:
            calls["pid"] = int(pid)

        def nice(self, value: int) -> None:
            calls["nice"] = int(value)

    monkeypatch.setenv(PROCESS_PRIORITY_ENV, PROCESS_PRIORITY_MODE_HIGH)
    monkeypatch.setattr(process_priority_module, "_is_windows_process_priority_supported", lambda: True)
    monkeypatch.setattr(process_priority_module.psutil, "Process", _FakeProcess)
    monkeypatch.setattr(
        process_priority_module.psutil,
        "HIGH_PRIORITY_CLASS",
        128,
        raising=False,
    )
    _reset_priority_cache()

    result = apply_process_priority_if_configured()

    assert result["mode"] == PROCESS_PRIORITY_MODE_HIGH
    assert result["source"] == "env"
    assert result["applied"] is True
    assert result["error"] is None
    assert calls["nice"] == 128


def test_apply_process_priority_reports_unsupported_platform_without_raising(monkeypatch) -> None:
    monkeypatch.setenv(PROCESS_PRIORITY_ENV, PROCESS_PRIORITY_MODE_HIGH)
    monkeypatch.setattr(process_priority_module, "_is_windows_process_priority_supported", lambda: False)
    _reset_priority_cache()

    result = apply_process_priority_if_configured()

    assert result["mode"] == PROCESS_PRIORITY_MODE_HIGH
    assert result["source"] == "env"
    assert result["applied"] is False
    assert str(result["error"]).startswith("unsupported_platform:")

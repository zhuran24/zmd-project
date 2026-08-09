"""Unit tests for src.runtime.campaign_freeze_monitor."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from src.runtime import campaign_freeze_monitor as cfm


def test_is_pacman_freeze_enabled_marker_present(tmp_path, monkeypatch):
    fake_conf = tmp_path / "pacman.conf"
    fake_conf.write_text(
        "# normal pacman.conf header\n"
        f"\n{cfm.FREEZE_MARKER}\n"
        "IgnorePkg = linux-cachyos glibc python\n"
        "# === Phase 3C campaign freeze END ===\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cfm, "PACMAN_CONF", fake_conf)
    assert cfm.is_pacman_freeze_enabled() is True


def test_is_pacman_freeze_enabled_marker_absent(tmp_path, monkeypatch):
    fake_conf = tmp_path / "pacman.conf"
    fake_conf.write_text("# pristine pacman.conf, no freeze\n", encoding="utf-8")
    monkeypatch.setattr(cfm, "PACMAN_CONF", fake_conf)
    assert cfm.is_pacman_freeze_enabled() is False


def test_is_pacman_freeze_enabled_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(cfm, "PACMAN_CONF", tmp_path / "does_not_exist")
    assert cfm.is_pacman_freeze_enabled() is False


def test_freeze_monitor_warns_when_marker_disappears(tmp_path, monkeypatch, capsys):
    """Start with freeze present, then remove mid-run; monitor must warn."""
    fake_conf = tmp_path / "pacman.conf"
    fake_conf.write_text(
        f"{cfm.FREEZE_MARKER}\nIgnorePkg = ...\n# === Phase 3C campaign freeze END ===\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cfm, "PACMAN_CONF", fake_conf)

    log_path = tmp_path / "telemetry.log"
    # Use a tiny interval so the test runs in <1s.
    stop_event = cfm.start_freeze_monitor(log_path=log_path, interval_seconds=1)

    # Let the monitor do one wait+check cycle while marker is still present
    time.sleep(0.3)
    # Now remove the marker by overwriting the file
    fake_conf.write_text("# freeze removed mid-run\n", encoding="utf-8")
    # Wait long enough for the monitor to detect the change
    time.sleep(1.4)
    stop_event.set()

    captured = capsys.readouterr()
    log_content = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    combined = captured.err + log_content
    assert "DISAPPEARED" in combined, (
        f"expected 'DISAPPEARED' warning in stderr or log, got:\n"
        f"  stderr={captured.err!r}\n  log={log_content!r}"
    )


def test_freeze_monitor_exits_silently_if_marker_missing_at_start(
    tmp_path, monkeypatch, capsys
):
    """If freeze isn't enabled when monitor starts, the monitor logs once
    and exits (caller should have caught this with the readiness gate)."""
    fake_conf = tmp_path / "pacman.conf"
    fake_conf.write_text("# no freeze\n", encoding="utf-8")
    monkeypatch.setattr(cfm, "PACMAN_CONF", fake_conf)

    log_path = tmp_path / "telemetry.log"
    cfm.start_freeze_monitor(log_path=log_path, interval_seconds=60)

    # Give it a moment to log the startup-state warning and exit
    time.sleep(0.2)

    captured = capsys.readouterr()
    log_content = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    combined = captured.err + log_content
    assert "startup state" in combined and "NOT present" in combined, (
        f"expected startup-state warning, got:\n  stderr={captured.err!r}\n"
        f"  log={log_content!r}"
    )


def test_freeze_monitor_thread_is_daemon(tmp_path, monkeypatch):
    """Daemon threads don't block process exit — verify the property."""
    fake_conf = tmp_path / "pacman.conf"
    fake_conf.write_text(f"{cfm.FREEZE_MARKER}\n", encoding="utf-8")
    monkeypatch.setattr(cfm, "PACMAN_CONF", fake_conf)

    cfm.start_freeze_monitor(log_path=None, interval_seconds=60)
    # Find the monitor thread
    monitor_threads = [t for t in threading.enumerate() if t.name == "campaign_freeze_monitor"]
    assert len(monitor_threads) >= 1
    assert all(t.daemon for t in monitor_threads), "monitor threads must be daemon"

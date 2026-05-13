"""P1 #24 follow-up: production_readiness_gate OOM headroom check tests.

Triggered by 2026-05-14 baseline 30-min run aborting at 9 min via
worker_process_failed → dmesg global_oom kill (4 worker × ~8 GB anon-rss
overshot 48 GB RAM). Gate now BLOCKs if estimated peak RSS exceeds
available memory.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import production_readiness_gate as prg  # noqa: E402


def _make_gate() -> prg.Gate:
    return prg.Gate()


def _patched_meminfo(available_kib: int) -> mock._patch:
    return mock.patch.object(
        prg.Path,
        "read_text",
        return_value=f"MemTotal:  48000000 kB\nMemAvailable: {available_kib} kB\n",
        autospec=False,
    )


def test_oom_headroom_ok_when_plenty_ram(monkeypatch):
    """128 GB free, 2 worker → needed=2×30+8=68 GB ≤ available, OK."""
    monkeypatch.setenv("EXACT_PARALLEL_PROCESSES", "2")
    with _patched_meminfo(128 * 1024 * 1024):
        gate = _make_gate()
        prg.check_oom_headroom(gate)
    assert any(level == "OK" and label == "OOM headroom" for level, label, _ in gate.checks)
    assert not gate.has_block


def test_oom_headroom_block_when_overcommit(monkeypatch):
    """4 worker × 30 GB + 8 GB host = 128 GB > 41 GB available → BLOCK."""
    monkeypatch.setenv("EXACT_PARALLEL_PROCESSES", "4")
    with _patched_meminfo(41 * 1024 * 1024):
        gate = _make_gate()
        prg.check_oom_headroom(gate)
    blocked = [c for c in gate.checks if c[0] == "BLOCK" and c[1] == "OOM headroom"]
    assert len(blocked) == 1
    assert "global OOM" in blocked[0][2]
    assert gate.has_block


def test_oom_headroom_warn_when_tight(monkeypatch):
    """2 worker × 30 GB + 8 GB = 68 GB, available=72 GB → 94% threshold, WARN."""
    monkeypatch.setenv("EXACT_PARALLEL_PROCESSES", "2")
    with _patched_meminfo(72 * 1024 * 1024):
        gate = _make_gate()
        prg.check_oom_headroom(gate)
    warned = [c for c in gate.checks if c[0] == "WARN" and c[1] == "OOM headroom"]
    assert len(warned) == 1
    assert "tight margin" in warned[0][2]


def test_oom_headroom_default_parallel_when_env_missing(monkeypatch):
    """缺 EXACT_PARALLEL_PROCESSES → 缺省 4 → needed=128, available=41 → BLOCK."""
    monkeypatch.delenv("EXACT_PARALLEL_PROCESSES", raising=False)
    with _patched_meminfo(41 * 1024 * 1024):
        gate = _make_gate()
        prg.check_oom_headroom(gate)
    assert gate.has_block


def test_oom_headroom_invalid_env_falls_back_to_default(monkeypatch):
    """EXACT_PARALLEL_PROCESSES=garbage → fallback 4 → needed=128 > 41 → BLOCK."""
    monkeypatch.setenv("EXACT_PARALLEL_PROCESSES", "notanumber")
    with _patched_meminfo(41 * 1024 * 1024):
        gate = _make_gate()
        prg.check_oom_headroom(gate)
    assert gate.has_block


def test_oom_headroom_warn_when_meminfo_missing(monkeypatch):
    """/proc/meminfo unreadable → WARN, not BLOCK (Linux only utility)."""
    monkeypatch.setenv("EXACT_PARALLEL_PROCESSES", "4")
    with mock.patch.object(prg.Path, "read_text", side_effect=OSError("ENOENT")):
        gate = _make_gate()
        prg.check_oom_headroom(gate)
    warned = [c for c in gate.checks if c[0] == "WARN" and c[1] == "OOM headroom"]
    assert len(warned) == 1
    assert not gate.has_block


def test_oom_headroom_warn_when_meminfo_unparsable(monkeypatch):
    """MemAvailable line missing/garbled → WARN, not BLOCK."""
    monkeypatch.setenv("EXACT_PARALLEL_PROCESSES", "4")
    with mock.patch.object(
        prg.Path,
        "read_text",
        return_value="MemTotal: 48000000 kB\nSlab: 1234 kB\n",
        autospec=False,
    ):
        gate = _make_gate()
        prg.check_oom_headroom(gate)
    warned = [c for c in gate.checks if c[0] == "WARN" and c[1] == "OOM headroom"]
    assert len(warned) == 1
    assert not gate.has_block

"""Production readiness gate C1 OOM headroom tests."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest

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


@pytest.fixture(autouse=True)
def _clear_worker_peak_env(monkeypatch):
    monkeypatch.delenv("EXACT_MASTER_CP_SAT_WORKERS", raising=False)
    monkeypatch.delenv("EXACT_CP_SAT_WORKERS", raising=False)
    monkeypatch.delenv("EXACT_GATE_WORKER_PEAK_RSS_GIB", raising=False)


def _oom_message(gate: prg.Gate) -> str:
    return next(msg for _, label, msg in gate.checks if label == "OOM headroom")


def test_oom_headroom_ok_when_plenty_ram(monkeypatch):
    """Missing master-worker env uses conservative 47 GiB tier."""
    monkeypatch.setenv("EXACT_PARALLEL_PROCESSES", "2")
    with _patched_meminfo(128 * 1024 * 1024):
        gate = _make_gate()
        prg.check_oom_headroom(gate)
    assert any(level == "OK" and label == "OOM headroom" for level, label, _ in gate.checks)
    assert "2 × 47GB/worker" in _oom_message(gate)
    assert "unset" in _oom_message(gate)
    assert "current default workers=8; conservative 47GB tier" in _oom_message(gate)
    assert not gate.has_block


def test_oom_headroom_block_when_overcommit(monkeypatch):
    """4 processes × conservative 47 GiB + 8 GiB host exceeds 41 GiB."""
    monkeypatch.setenv("EXACT_PARALLEL_PROCESSES", "4")
    with _patched_meminfo(41 * 1024 * 1024):
        gate = _make_gate()
        prg.check_oom_headroom(gate)
    blocked = [c for c in gate.checks if c[0] == "BLOCK" and c[1] == "OOM headroom"]
    assert len(blocked) == 1
    assert "global OOM" in blocked[0][2]
    assert gate.has_block


def test_oom_headroom_warn_when_tight(monkeypatch):
    """w6 tier (steady-state 20G): 2 × 20 GiB + 8 GiB = 48 vs 52 GiB is tight."""
    monkeypatch.setenv("EXACT_PARALLEL_PROCESSES", "2")
    monkeypatch.setenv("EXACT_MASTER_CP_SAT_WORKERS", "6")
    with _patched_meminfo(52 * 1024 * 1024):
        gate = _make_gate()
        prg.check_oom_headroom(gate)
    warned = [c for c in gate.checks if c[0] == "WARN" and c[1] == "OOM headroom"]
    assert len(warned) == 1
    assert "tight margin" in warned[0][2]
    assert "2 × 20GB/worker" in warned[0][2]
    assert "w<=6 tier" in warned[0][2]


def test_oom_headroom_default_parallel_when_env_missing(monkeypatch):
    """缺 EXACT_PARALLEL_PROCESSES → 缺省 4 → needed=196, available=41 → BLOCK."""
    monkeypatch.delenv("EXACT_PARALLEL_PROCESSES", raising=False)
    with _patched_meminfo(41 * 1024 * 1024):
        gate = _make_gate()
        prg.check_oom_headroom(gate)
    assert gate.has_block


def test_oom_headroom_invalid_env_falls_back_to_default(monkeypatch):
    """EXACT_PARALLEL_PROCESSES=garbage → fallback 4 → needed=196 > 41 → BLOCK."""
    monkeypatch.setenv("EXACT_PARALLEL_PROCESSES", "notanumber")
    with _patched_meminfo(41 * 1024 * 1024):
        gate = _make_gate()
        prg.check_oom_headroom(gate)
    assert gate.has_block
    assert "parallel=4" in _oom_message(gate)


@pytest.mark.parametrize("parallel", ["0", "-1"])
def test_oom_headroom_parallel_is_clamped_to_one(monkeypatch, parallel):
    monkeypatch.setenv("EXACT_PARALLEL_PROCESSES", parallel)
    monkeypatch.setenv("EXACT_MASTER_CP_SAT_WORKERS", "6")
    with _patched_meminfo(128 * 1024 * 1024):
        gate = _make_gate()
        prg.check_oom_headroom(gate)
    assert "parallel=1 × 20GB/worker" in _oom_message(gate)


@pytest.mark.parametrize(
    ("master_workers", "tier_note"),
    [("7", "6<w<=12 tier"), ("12", "6<w<=12 tier"), ("13", "w>12 tier")],
)
def test_oom_headroom_worker_peak_tiers(monkeypatch, master_workers, tier_note):
    monkeypatch.setenv("EXACT_PARALLEL_PROCESSES", "1")
    monkeypatch.setenv("EXACT_MASTER_CP_SAT_WORKERS", master_workers)
    with _patched_meminfo(128 * 1024 * 1024):
        gate = _make_gate()
        prg.check_oom_headroom(gate)
    message = _oom_message(gate)
    assert "1 × 47GB/worker" in message
    assert tier_note in message


@pytest.mark.parametrize(
    ("env_name", "workers"),
    [
        ("EXACT_MASTER_CP_SAT_WORKERS", "notanumber"),
        ("EXACT_MASTER_CP_SAT_WORKERS", "0"),
        ("EXACT_MASTER_CP_SAT_WORKERS", "-1"),
        ("EXACT_CP_SAT_WORKERS", "notanumber"),
        ("EXACT_CP_SAT_WORKERS", "0"),
        ("EXACT_CP_SAT_WORKERS", "-1"),
    ],
)
def test_oom_headroom_invalid_worker_env_uses_conservative_tier(
    monkeypatch, env_name, workers
):
    monkeypatch.setenv("EXACT_PARALLEL_PROCESSES", "1")
    monkeypatch.setenv(env_name, workers)
    with _patched_meminfo(128 * 1024 * 1024):
        gate = _make_gate()
        prg.check_oom_headroom(gate)
    message = _oom_message(gate)
    assert "1 × 47GB/worker" in message
    assert "invalid" in message
    assert "current default workers=8; conservative 47GB tier" in message


def test_oom_headroom_global_worker_env_selects_w6_tier(monkeypatch):
    monkeypatch.setenv("EXACT_PARALLEL_PROCESSES", "1")
    monkeypatch.setenv("EXACT_CP_SAT_WORKERS", "6")
    with _patched_meminfo(128 * 1024 * 1024):
        gate = _make_gate()
        prg.check_oom_headroom(gate)
    message = _oom_message(gate)
    assert "1 × 20GB/worker" in message
    assert "source=EXACT_CP_SAT_WORKERS" in message


def test_oom_headroom_master_worker_env_takes_priority_over_global(monkeypatch):
    monkeypatch.setenv("EXACT_PARALLEL_PROCESSES", "1")
    monkeypatch.setenv("EXACT_MASTER_CP_SAT_WORKERS", "12")
    monkeypatch.setenv("EXACT_CP_SAT_WORKERS", "6")
    with _patched_meminfo(128 * 1024 * 1024):
        gate = _make_gate()
        prg.check_oom_headroom(gate)
    message = _oom_message(gate)
    assert "1 × 47GB/worker" in message
    assert "source=EXACT_MASTER_CP_SAT_WORKERS" in message


def test_oom_headroom_peak_override_covers_worker_tier(monkeypatch):
    monkeypatch.setenv("EXACT_PARALLEL_PROCESSES", "1")
    monkeypatch.setenv("EXACT_MASTER_CP_SAT_WORKERS", "6")
    monkeypatch.setenv("EXACT_GATE_WORKER_PEAK_RSS_GIB", "23")
    with _patched_meminfo(128 * 1024 * 1024):
        gate = _make_gate()
        prg.check_oom_headroom(gate)
    message = _oom_message(gate)
    assert "1 × 23GB/worker" in message
    assert "w<=6 tier" in message


@pytest.mark.parametrize(
    "peak_override", ["notanumber", "0", "-1", "nan", "inf", "-inf"]
)
def test_oom_headroom_invalid_peak_override_falls_back_to_worker_tier(
    monkeypatch, peak_override
):
    monkeypatch.setenv("EXACT_PARALLEL_PROCESSES", "1")
    monkeypatch.setenv("EXACT_MASTER_CP_SAT_WORKERS", "6")
    monkeypatch.setenv("EXACT_GATE_WORKER_PEAK_RSS_GIB", peak_override)
    with _patched_meminfo(128 * 1024 * 1024):
        gate = _make_gate()
        prg.check_oom_headroom(gate)
    assert "1 × 20GB/worker" in _oom_message(gate)


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

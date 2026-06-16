"""Unit tests for src.runtime.subproblem_invocation_counter (P1 #12 spike)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.runtime import subproblem_invocation_counter as sic


def test_record_no_op_when_env_unset(tmp_path, monkeypatch):
    monkeypatch.delenv("EXACT_SUBPROBLEM_REPEAT_PROBE", raising=False)
    counter = sic.SubproblemInvocationCounter(log_path=tmp_path / "x.jsonl")
    counter.record("binding", {"key": 1})
    counter.record("binding", {"key": 1})
    summary = counter.summary()
    assert summary == {}


def test_record_counts_repeats_when_env_on(tmp_path, monkeypatch):
    monkeypatch.setenv("EXACT_SUBPROBLEM_REPEAT_PROBE", "1")
    counter = sic.SubproblemInvocationCounter(log_path=tmp_path / "x.jsonl")
    counter.record("binding", {"a": 1})
    counter.record("binding", {"a": 1})
    counter.record("binding", {"a": 2})
    counter.record("routing", {"a": 1})
    summary = counter.summary()
    assert summary["binding"]["total"] == 3
    assert summary["binding"]["unique"] == 2
    assert summary["binding"]["repeat_rate"] == pytest.approx(1.0 - 2 / 3)
    assert summary["binding"]["max_repeats"] == 2
    assert summary["routing"]["total"] == 1
    assert summary["routing"]["unique"] == 1
    assert summary["routing"]["repeat_rate"] == 0.0


def test_canonical_hash_order_independent(monkeypatch):
    monkeypatch.setenv("EXACT_SUBPROBLEM_REPEAT_PROBE", "1")
    counter = sic.SubproblemInvocationCounter()
    counter.record("binding", {"a": 1, "b": 2})
    counter.record("binding", {"b": 2, "a": 1})  # same content, diff order
    summary = counter.summary()
    # Both should hash to the same key → 1 unique, 2 total
    assert summary["binding"]["total"] == 2
    assert summary["binding"]["unique"] == 1


def test_dump_writes_jsonl(tmp_path, monkeypatch):
    monkeypatch.setenv("EXACT_SUBPROBLEM_REPEAT_PROBE", "1")
    log_path = tmp_path / "tel" / "out.jsonl"
    counter = sic.SubproblemInvocationCounter(
        log_path=log_path,
        dump_interval_seconds=0.0,  # always dump on next record
    )
    counter.record("binding", {"a": 1})
    # First record won't dump (last_dump set to monotonic at init), so call
    # explicit dump_now to verify file path/format.
    counter.dump_now()
    assert log_path.exists()
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 1
    rec = json.loads(lines[-1])
    assert "timestamp" in rec
    assert "pid" in rec
    assert rec["summary"]["binding"]["total"] == 1


def test_dump_now_no_op_without_log_path(monkeypatch):
    monkeypatch.setenv("EXACT_SUBPROBLEM_REPEAT_PROBE", "1")
    counter = sic.SubproblemInvocationCounter(log_path=None)
    counter.record("binding", {"a": 1})
    counter.dump_now()  # should not raise


def test_module_record_helper_is_env_gated(tmp_path, monkeypatch):
    monkeypatch.delenv("EXACT_SUBPROBLEM_REPEAT_PROBE", raising=False)
    monkeypatch.setattr(sic, "_GLOBAL_COUNTER", None)
    sic.record("binding", {"a": 1})
    # Counter should not have been initialized.
    assert sic._GLOBAL_COUNTER is None


def test_is_enabled_reflects_env(monkeypatch):
    monkeypatch.delenv("EXACT_SUBPROBLEM_REPEAT_PROBE", raising=False)
    assert sic.is_enabled() is False
    monkeypatch.setenv("EXACT_SUBPROBLEM_REPEAT_PROBE", "yes")
    assert sic.is_enabled() is True

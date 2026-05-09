"""Tests for src.search.master_hint_persistence (P1 #7e prep)."""

from __future__ import annotations

import json

import pytest

from src.search import master_hint_persistence as mhp


def test_is_enabled_env_gated(monkeypatch):
    monkeypatch.delenv(mhp.HINT_PERSISTENCE_ENV, raising=False)
    assert mhp.is_enabled() is False
    monkeypatch.setenv(mhp.HINT_PERSISTENCE_ENV, "1")
    assert mhp.is_enabled() is True
    monkeypatch.setenv(mhp.HINT_PERSISTENCE_ENV, "yes")
    assert mhp.is_enabled() is True
    monkeypatch.setenv(mhp.HINT_PERSISTENCE_ENV, "0")
    assert mhp.is_enabled() is False


def test_write_then_load_roundtrip(tmp_path):
    var_values = {"x_0": 1, "x_1": 0, "y_5_3": 1}
    written = mhp.write_master_hints(tmp_path, "70x70", var_values)
    assert written.exists()
    loaded = mhp.load_master_hints(tmp_path, "70x70")
    assert loaded == var_values


def test_load_returns_none_when_missing(tmp_path):
    assert mhp.load_master_hints(tmp_path, "nonexistent") is None


def test_load_returns_none_on_bad_json(tmp_path):
    path = mhp.hint_path(tmp_path, "70x70")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ this is not valid json", encoding="utf-8")
    assert mhp.load_master_hints(tmp_path, "70x70") is None


def test_load_returns_none_on_wrong_schema_version(tmp_path):
    path = mhp.hint_path(tmp_path, "70x70")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"schema_version": 999, "var_values": {"x": 1}}),
        encoding="utf-8",
    )
    assert mhp.load_master_hints(tmp_path, "70x70") is None


def test_clear_removes_file(tmp_path):
    mhp.write_master_hints(tmp_path, "70x70", {"x": 1})
    assert mhp.clear_master_hints(tmp_path, "70x70") is True
    assert mhp.load_master_hints(tmp_path, "70x70") is None
    assert mhp.clear_master_hints(tmp_path, "70x70") is False


def test_sanitize_rejects_path_separator(tmp_path):
    with pytest.raises(ValueError):
        mhp.write_master_hints(tmp_path, "../escape", {"x": 1})
    with pytest.raises(ValueError):
        mhp.write_master_hints(tmp_path, "70x70/extra", {"x": 1})


def test_sanitize_rejects_empty(tmp_path):
    with pytest.raises(ValueError):
        mhp.write_master_hints(tmp_path, "", {"x": 1})


def test_overwrite_replaces_fully(tmp_path):
    mhp.write_master_hints(tmp_path, "70x70", {"x": 1, "y": 0})
    mhp.write_master_hints(tmp_path, "70x70", {"z": 1})
    loaded = mhp.load_master_hints(tmp_path, "70x70")
    assert loaded == {"z": 1}


def test_write_payload_format(tmp_path):
    mhp.write_master_hints(tmp_path, "70x70", {"x": 5})
    raw = mhp.hint_path(tmp_path, "70x70").read_text(encoding="utf-8")
    payload = json.loads(raw)
    assert payload["candidate_key"] == "70x70"
    assert payload["schema_version"] == mhp.HINT_SCHEMA_VERSION
    assert "saved_at" in payload
    assert payload["var_values"] == {"x": 5}

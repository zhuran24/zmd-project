"""Tests for P1 #7 main #1+#2 — master hint cross-wave loop integration.

Covers MasterPlacementModel.set_hint_persistence_context + the auto
load/save hooks (_maybe_load_hints_from_persistence /
_maybe_save_hints_to_persistence). 不构造完整 master (复杂),
直接用 stub-pattern 调 method.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.models.master_model import MasterPlacementModel
from src.search import master_hint_persistence as mhp


def _make_stub(*, solver=None, status=None, ctx=None, exact_mode=False):
    """Lightweight master stub exposing the attributes the hint hooks read."""
    obj = type("MasterStub", (), {})()
    obj._solver = solver
    obj._status = status
    obj._hint_persistence_context = ctx
    obj.exact_mode = exact_mode
    obj._coordinate_delegate = None
    obj._built = True
    obj.z_vars = {}
    obj.optional_pose_vars = {}
    obj.model = None
    return obj


def test_set_hint_persistence_context_stores_tuple(tmp_path):
    obj = _make_stub()
    MasterPlacementModel.set_hint_persistence_context(obj, tmp_path, "70x70")
    assert obj._hint_persistence_context == (tmp_path, "70x70")


def test_set_hint_persistence_context_none_disables(tmp_path):
    obj = _make_stub(ctx=(tmp_path, "70x70"))
    MasterPlacementModel.set_hint_persistence_context(obj, None, "70x70")
    assert obj._hint_persistence_context is None
    MasterPlacementModel.set_hint_persistence_context(obj, tmp_path, None)
    assert obj._hint_persistence_context is None


def test_maybe_load_no_op_when_env_off(tmp_path, monkeypatch):
    monkeypatch.delenv(mhp.HINT_PERSISTENCE_ENV, raising=False)
    # Pre-write a hint file; env off -> should NOT load.
    mhp.write_master_hints(tmp_path, "70x70", {"x": 1})
    obj = _make_stub(ctx=(tmp_path, "70x70"))
    n = MasterPlacementModel._maybe_load_hints_from_persistence(obj)
    assert n == 0


def test_maybe_load_no_op_when_no_context(tmp_path, monkeypatch):
    monkeypatch.setenv(mhp.HINT_PERSISTENCE_ENV, "1")
    obj = _make_stub(ctx=None)
    n = MasterPlacementModel._maybe_load_hints_from_persistence(obj)
    assert n == 0


def test_maybe_load_returns_zero_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setenv(mhp.HINT_PERSISTENCE_ENV, "1")
    obj = _make_stub(ctx=(tmp_path, "70x70"))
    n = MasterPlacementModel._maybe_load_hints_from_persistence(obj)
    assert n == 0


def test_maybe_save_no_op_when_env_off(tmp_path, monkeypatch):
    from ortools.sat.python import cp_model
    monkeypatch.delenv(mhp.HINT_PERSISTENCE_ENV, raising=False)
    obj = _make_stub(
        solver=type("S", (), {})(),
        status=cp_model.FEASIBLE,
        ctx=(tmp_path, "70x70"),
    )
    n = MasterPlacementModel._maybe_save_hints_to_persistence(obj)
    assert n == 0
    # No file should be written
    assert not mhp.hint_path(tmp_path, "70x70").exists()


def test_maybe_save_no_op_when_no_context(monkeypatch):
    from ortools.sat.python import cp_model
    monkeypatch.setenv(mhp.HINT_PERSISTENCE_ENV, "1")
    obj = _make_stub(
        solver=type("S", (), {})(),
        status=cp_model.FEASIBLE,
        ctx=None,
    )
    n = MasterPlacementModel._maybe_save_hints_to_persistence(obj)
    assert n == 0


def test_maybe_save_no_op_when_status_unknown(tmp_path, monkeypatch):
    from ortools.sat.python import cp_model
    monkeypatch.setenv(mhp.HINT_PERSISTENCE_ENV, "1")
    obj = _make_stub(
        solver=type("S", (), {})(),
        status=cp_model.UNKNOWN,
        ctx=(tmp_path, "70x70"),
    )
    n = MasterPlacementModel._maybe_save_hints_to_persistence(obj)
    assert n == 0
    assert not mhp.hint_path(tmp_path, "70x70").exists()


def test_extract_master_hints_returns_empty_when_no_solver():
    obj = _make_stub(solver=None, status=None)
    out = MasterPlacementModel.extract_master_hints(obj)
    assert out == {}


def test_extract_master_hints_exact_delegate_no_method():
    """exact_mode 但 delegate 没实现 extract_master_hints → 返 {}."""
    from ortools.sat.python import cp_model
    obj = _make_stub(
        solver=type("S", (), {})(),
        status=cp_model.FEASIBLE,
        exact_mode=True,
    )
    obj._coordinate_delegate = type("Delegate", (), {})()  # no extract method
    out = MasterPlacementModel.extract_master_hints(obj)
    assert out == {}


def test_apply_master_hints_no_op_when_not_built(tmp_path):
    obj = _make_stub()
    obj._built = False
    n = MasterPlacementModel.apply_master_hints(obj, {"x": 1})
    assert n == 0


def test_apply_master_hints_no_op_when_empty(tmp_path):
    obj = _make_stub()
    n = MasterPlacementModel.apply_master_hints(obj, {})
    assert n == 0

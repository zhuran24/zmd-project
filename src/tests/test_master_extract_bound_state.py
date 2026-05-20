"""Tests for P1 #7 main — MasterPlacementModel.extract_bound_state."""

from __future__ import annotations

from src.models.master_model import MasterPlacementModel


class _StubSolver:
    """Mimics cp_model.CpSolver subset used by extract_bound_state."""

    def __init__(self, *, best_bound=None, objective=None):
        self._best_bound = best_bound
        self._objective = objective

    def BestObjectiveBound(self):
        if self._best_bound is None:
            raise RuntimeError("no bound")
        return self._best_bound

    def ObjectiveValue(self):
        if self._objective is None:
            raise RuntimeError("no objective")
        return self._objective


def _make_master_with_solver(stub_solver, status):
    """Construct a minimal MasterPlacementModel-like object exposing the
    fields extract_bound_state needs. We avoid full master construction
    (too heavy) by binding the unbound method onto a SimpleNamespace."""
    obj = type("MasterStub", (), {})()
    obj._solver = stub_solver
    obj._status = status
    return obj


def test_extract_bound_state_no_solver_returns_all_none():
    obj = _make_master_with_solver(None, 0)
    out = MasterPlacementModel.extract_bound_state(obj)
    assert out["lb"] is None
    assert out["ub"] is None
    assert out["gap"] is None
    assert out["prover"] == "master_cpsat"


def test_extract_bound_state_optimal_lb_eq_ub_zero_gap():
    from ortools.sat.python import cp_model
    stub = _StubSolver(best_bound=100, objective=100)
    obj = _make_master_with_solver(stub, cp_model.OPTIMAL)
    out = MasterPlacementModel.extract_bound_state(obj)
    assert out["lb"] == 100
    assert out["ub"] == 100
    assert out["gap"] == 0.0


def test_extract_bound_state_feasible_with_gap():
    from ortools.sat.python import cp_model
    stub = _StubSolver(best_bound=80, objective=100)
    obj = _make_master_with_solver(stub, cp_model.FEASIBLE)
    out = MasterPlacementModel.extract_bound_state(obj)
    assert out["lb"] == 80
    assert out["ub"] == 100
    # gap = (100 - 80) / max(|100|, 1) = 0.2
    assert abs(out["gap"] - 0.2) < 1e-9


def test_extract_bound_state_unknown_no_incumbent():
    """status=UNKNOWN: ObjectiveValue 不可调, lb 仍能拿."""
    from ortools.sat.python import cp_model
    stub = _StubSolver(best_bound=50, objective=None)
    obj = _make_master_with_solver(stub, cp_model.UNKNOWN)
    out = MasterPlacementModel.extract_bound_state(obj)
    assert out["lb"] == 50
    assert out["ub"] is None
    assert out["gap"] is None  # 缺 ub 算不出 gap


def test_extract_bound_state_passes_epsilon_target():
    obj = _make_master_with_solver(None, 0)
    out = MasterPlacementModel.extract_bound_state(obj, epsilon_target=0.05)
    assert out["epsilon_target"] == 0.05


def test_extract_bound_state_default_epsilon_target_none():
    obj = _make_master_with_solver(None, 0)
    out = MasterPlacementModel.extract_bound_state(obj)
    assert out["epsilon_target"] is None

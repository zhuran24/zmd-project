"""Depth-defense: binding overload separation can be forced OFF by caller, and
I1 independent reverify does force it OFF regardless of env.

Before this, PortBindingModel.build() only read EXACT_BINDING_USE_OVERLOAD_SEPARATION
from the env, so I1's independently-rebuilt binding model inherited the same
heuristic HARD nogood (which can cut feasible solutions) whenever that env was
set — a depth-defense gap (the env is not on the certified operational allowlist,
so it is fail-closed at the certified entry, but I1 should not depend on that).
build() now takes an explicit override; I1 passes use_overload_separation=False.
"""

from __future__ import annotations

from pathlib import Path

from src.models.binding_subproblem import PortBindingModel
from src.search import independent_infeasibility_reverifier as iir

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _minimal_binding() -> PortBindingModel:
    # Pass explicit empty generic io so __init__ does not read io_requirements.
    return PortBindingModel(
        placement_solution={},
        facility_pools={},
        instances=[],
        required_generic_outputs={},
        required_generic_inputs={},
    )


def test_build_override_false_forces_off_even_with_env(monkeypatch):
    monkeypatch.setenv("EXACT_BINDING_USE_OVERLOAD_SEPARATION", "1")
    model = _minimal_binding()
    model.build(use_overload_separation=False)
    assert model.extract_conflict_summary()["overload_separation_enabled"] is False


def test_build_override_true_forces_on_even_without_env(monkeypatch):
    monkeypatch.delenv("EXACT_BINDING_USE_OVERLOAD_SEPARATION", raising=False)
    model = _minimal_binding()
    model.build(use_overload_separation=True)
    assert model.extract_conflict_summary()["overload_separation_enabled"] is True


def test_build_none_reads_env(monkeypatch):
    monkeypatch.setenv("EXACT_BINDING_USE_OVERLOAD_SEPARATION", "1")
    on = _minimal_binding()
    on.build()
    assert on.extract_conflict_summary()["overload_separation_enabled"] is True

    monkeypatch.delenv("EXACT_BINDING_USE_OVERLOAD_SEPARATION", raising=False)
    off = _minimal_binding()
    off.build()
    assert off.extract_conflict_summary()["overload_separation_enabled"] is False


def test_i1_reverify_binding_forces_overload_off(monkeypatch):
    """I1's independent binding rebuild must pass use_overload_separation=False
    even when the env is set on (so the reverifier never inherits the nogood)."""
    monkeypatch.setenv("EXACT_BINDING_USE_OVERLOAD_SEPARATION", "1")
    captured = {}
    original_build = PortBindingModel.build

    def spy_build(self, *, use_overload_separation=None):
        captured["use_overload_separation"] = use_overload_separation
        return original_build(self, use_overload_separation=use_overload_separation)

    monkeypatch.setattr(PortBindingModel, "build", spy_build)

    iir._reverify_binding_infeasible(
        solution={},
        facility_pools={},
        instances=[],
        project_root=_REPO_ROOT,
        binding_kwargs=None,
        time_limit_seconds=5.0,
    )
    assert captured.get("use_overload_separation") is False

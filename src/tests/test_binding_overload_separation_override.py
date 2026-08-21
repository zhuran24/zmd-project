"""Depth-defense for the production overload-separation switch.

``PortBindingModel.build()`` still supports an explicit override so certified
fallback code can re-run the production model without the heuristic HARD
nogoods.  I1 no longer rebuilds this model at all: its capability contract reads
the producing model's observed ``overload_separation_enabled`` field and the
closed-world verifier rejects ``True`` fail-closed.
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


def test_i1_reverify_binding_has_no_production_model_or_env_dependency(monkeypatch):
    """I1 no longer rebuilds the production model, so the overload env is inert."""

    monkeypatch.setenv("EXACT_BINDING_USE_OVERLOAD_SEPARATION", "1")
    assert not hasattr(iir, "PortBindingModel")
    source = Path(iir.__file__).read_text(encoding="utf-8")
    assert "from src.models" not in source
    assert "from ortools" not in source
    assert "os.environ" not in source

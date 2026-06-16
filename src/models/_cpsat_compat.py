"""Cross-version helpers for OR-Tools CP-SAT surfaces.

These shims keep the certified codepath stable across the currently locked
runtime (`ortools==9.15.6755`) and older pre-9.15 builds that expose a slightly
narrower Python API surface.

Two compatibility gaps matter here:

1. `search_branching`
   - ortools >= 9.15 often stringifies to a named enum such as
     ``SearchBranching.FIXED_SEARCH``.
   - older builds can expose the same value as a plain integer like ``1``.

2. `CpModel(model_proto=...)`
   - supported in newer builds.
   - older builds raise ``TypeError`` and require an empty model followed by a
     proto copy.
"""

from __future__ import annotations

from typing import Any

from ortools.sat.python import cp_model

_SEARCH_BRANCHING_NAMES: dict[int, str] = {}
for _name in (
    "AUTOMATIC_SEARCH",
    "FIXED_SEARCH",
    "PORTFOLIO_SEARCH",
    "LP_SEARCH",
    "PSEUDO_COST_SEARCH",
    "PORTFOLIO_WITH_QUICK_RESTART_SEARCH",
):
    _value = getattr(cp_model, _name, None)
    if _value is None:
        continue
    try:
        _SEARCH_BRANCHING_NAMES[int(_value)] = _name
    except Exception:
        continue


def search_branching_name(value: Any) -> str:
    """Return a stable, human-readable search branching name.

    Examples:
    - ``SearchBranching.FIXED_SEARCH`` -> ``"SearchBranching.FIXED_SEARCH"``
    - ``1`` or ``"1"`` -> ``"FIXED_SEARCH"`` when that enum is known
    """

    if value is None:
        return ""

    rendered = str(value)
    try:
        numeric_value = int(value)
    except Exception:
        return rendered

    if isinstance(value, int) or rendered.isdigit():
        return _SEARCH_BRANCHING_NAMES.get(numeric_value, rendered)

    return rendered


def _copy_model_proto(dst_model: Any, model_proto: Any) -> None:
    """Copy a model proto into an existing ``CpModel``-like object."""

    proto_target = getattr(dst_model, "proto", None)
    if callable(proto_target):
        proto_target = proto_target()
    if proto_target is None and hasattr(dst_model, "Proto"):
        try:
            proto_target = dst_model.Proto()
        except Exception:
            proto_target = None

    if proto_target is None:
        raise TypeError("Destination CpModel surface does not expose a writable proto handle")

    copier = getattr(proto_target, "CopyFrom", None)
    if callable(copier):
        copier(model_proto)
        return

    copier = getattr(proto_target, "copy_from", None)
    if callable(copier):
        copier(model_proto)
        return

    raise TypeError("Destination CpModel proto surface does not support copy_from / CopyFrom")



def cp_model_from_proto(model_proto: Any) -> cp_model.CpModel:
    """Build a ``CpModel`` from a proto across old and new OR-Tools versions."""

    try:
        return cp_model.CpModel(model_proto=model_proto)
    except TypeError:
        model = cp_model.CpModel()
        _copy_model_proto(model, model_proto)
        return model

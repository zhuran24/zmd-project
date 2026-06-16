# -*- coding: utf-8 -*-
"""Shared source-of-truth (SoT) cross-checks for cut-family validators.

Centralizes the "read a canonical scalar / footprint from
``state.canonical_rules``, fail-closed on any miss" pattern so that every cut
family which trusts a canonical-derivable value reuses ONE implementation
instead of carrying a private (and potentially divergent) copy.

Why this exists: the v28 GPT pro review found that F7 trusted ``pole_radius``
and F7/F8 trusted hard-coded footprints without cross-checking canonical_rules
(fail-open). The fix was the same shape in several places; keeping one copy
here means a future family cannot silently diverge. Coverage is asserted by
``src/tests/cuts/test_canonical_sot_coverage.py``; see PROJECT_LOCK §3
"cut-family validator 数值/字面量 source-of-truth gate".
"""
from __future__ import annotations

import time
from typing import Literal, Optional, Tuple, cast

from src.cuts.lifecycle import BState, ValidationResult

# Mirrors the per-family local alias (families define this Literal locally, not in lifecycle).
ValidationKind = Literal["ok", "unsound", "timeout", "schema_err"]


def _is_strict_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _vr(kind: ValidationKind, t0: float, detail: str) -> ValidationResult:
    return ValidationResult(kind=kind, elapsed_seconds=time.monotonic() - t0, detail=detail or None)


def lookup_canonical_pole_radius(state: BState) -> Optional[float]:
    """``facility_templates.power_pole.power_coverage_radius``; None on any miss (fail-closed)."""
    rules = state.canonical_rules
    if not isinstance(rules, dict):
        return None
    templates = rules.get("facility_templates")
    if not isinstance(templates, dict):
        return None
    pole_tpl = templates.get("power_pole")
    if not isinstance(pole_tpl, dict):
        return None
    radius = pole_tpl.get("power_coverage_radius")
    if isinstance(radius, bool):
        return None
    if not isinstance(radius, (int, float)):
        return None
    return float(radius)


def lookup_canonical_template_dims(state: BState, template_id: str) -> Optional[Tuple[int, int]]:
    """``facility_templates[template_id].dimensions`` -> (w, h); None on any miss (fail-closed)."""
    rules = state.canonical_rules
    if not isinstance(rules, dict):
        return None
    templates = rules.get("facility_templates")
    if not isinstance(templates, dict):
        return None
    tpl = templates.get(template_id)
    if not isinstance(tpl, dict):
        return None
    dims = tpl.get("dimensions")
    if not isinstance(dims, dict):
        return None
    w_raw = dims.get("w")
    h_raw = dims.get("h")
    if not _is_strict_int(w_raw) or not _is_strict_int(h_raw):
        return None
    return (cast(int, w_raw), cast(int, h_raw))


def validate_template_dims_sot(
    state: BState, template_id: str, expected: Tuple[int, int], t0: float
) -> Optional[ValidationResult]:
    """Fail-closed: canonical footprint for ``template_id`` must equal the validator-locked dims."""
    dims = lookup_canonical_template_dims(state, template_id)
    if dims is None:
        return _vr(
            "unsound",
            t0,
            f"state.canonical_rules.facility_templates.{template_id}.dimensions missing "
            "— cannot verify footprint against source-of-truth (fail-closed)",
        )
    if dims != expected:
        return _vr(
            "unsound",
            t0,
            f"canonical {template_id} dimensions {dims[0]}x{dims[1]} != validator-locked "
            f"{expected[0]}x{expected[1]}",
        )
    return None
